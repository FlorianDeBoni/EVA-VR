# EVA-VR

A chatbot-led design workshop whose goal is to **imagine and design a room that boosts creativity**.
The user talks to an assistant; the workshop moves through steps, and each step has its own
assistant, its own prompt and its own tools. The assistant also speaks to the user through
images (references, generated concepts).

| Step | Name | Ends when | Stored in the database |
|------|------|-----------|------------------------|
| 1 | Information gathering | the user confirms the summary of their answers | the `session` row (`is_validated`) |
| 2 | Concept design | the user accepts a generated concept image | `session.concept_image` + `concept_design_validated` |

Everything below describes what each step does and why. For setup, jump to [Run it](#run-it).

## How a conversation works

- **The API keeps no history.** The browser owns the conversation: every `POST /chat` carries the
  whole message list (texts only) and the `session_id`. Everything that must survive between turns
  (gathered information, images, validation flags) is in the database.
- **One graph, one subgraph per step.** The main graph (LangGraph) is a router in front of the
  subgraphs. Each subgraph is a small agent: *model ⇄ tools*, repeated until the model answers
  without calling a tool. All of them share the same state (`GraphState`).
- **The current step is derived, never stored.** `current_step(state)` (`backend/src/graph/steps.py`)
  gives step 1 until the information is validated, step 2 after. The router and the API answer
  (`step`) both use it, so they cannot disagree.
- **Steps chain inside one turn.** When the user confirms in step 1, the turn does not end: the
  graph continues straight into step 2, which speaks next. The `step` in that very answer is
  already `2`.
- **Prompts live in Langfuse**, one markdown file per step in `infrastructure/langfuse/prompts/`,
  published by `task seed:prompts`. Edit them in Langfuse to tune the assistants without redeploying.

```
START ──router──► gather_information ──(information validated?)──► concept_design ──► END
            └────────────────────────────────────────────────────────►┘
```

## Step 1: Information gathering

**Assistant:** warm, curious and short. It only listens and asks; it does not suggest designs.
**Prompt:** `information_gathering`. **Code:** `backend/src/graph/subgraphs/information_gathering/`.

**What it must find out** (`InformationToGather`):

| Field | Meaning |
|-------|---------|
| `user_type` | who will use the room (a team of architects, school children, a band…) |
| `number_of_users` | how many people use it at the same time |
| `task_description` | the creative task done in the room |
| `goal` | what the person wants to achieve with that task |
| `must_have_features` | optional features the room must have; asked once, never insisted on |
| `is_validated` | set by the assistant after the user's confirmation |

**Behavior**

1. **Opening.** With an empty message list, the assistant speaks first: a short welcome, then its
   first question (who will use the room).
2. **One question at a time**, in the language the user writes in. If an answer is vague it asks a
   short follow-up and never invents information. Several answers in one message are all taken in.
3. **Recording comes first.** Whenever a message contains anything about the fields above, the
   assistant calls `update_information` *before* replying, with every changed field in one call. The
   data is saved to the database immediately. Changing anything resets `is_validated`.
4. **Validation.** Once the four required fields are known and must-have features were asked about,
   the assistant summarizes in a few lines and asks for confirmation. Only after a clear yes does it
   call `validate_information`, never in the same turn as the summary. The tool refuses if a
   required field is still missing; the assistant then keeps asking.
5. **Hand-over.** The step ends right after `validate_information` succeeds. The assistant writes
   nothing more: step 2 answers in the same turn.

**Tools:** `update_information`, `validate_information` (parallel tool calls are disabled: two
simultaneous writes would overwrite each other).

## Step 2: Concept design

**Assistant:** a visual design partner that looks at the images and listens. It works on the
**overall design only** (volume and shape, spatial organisation, mood, palette, main materials,
light). Details such as furniture, equipment or dimensions are acknowledged and deferred to a later
step. **Prompt:** `concept_design`. **Code:** `backend/src/graph/subgraphs/concept_design/`.

**Phase 1: reference images**

- On entry, if no references exist, the assistant's first action is `search_web_images`. It builds
  `query` (3 to 6 English keywords) and `criteria` (what a good reference looks like) from the
  step-1 information: kind of users, headcount, task, goal, must-have features.
- The tool searches the web, has a vision model **rank** the candidates against the criteria,
  downloads the best ones (skipping dead links and non-images) and keeps **3**. They are saved as
  *Reference 1 to 3*, base64, in `concept_reference_images`. Calling the tool again replaces them.
- Downloads are untrusted: only public http(s) hosts (redirects checked), a size cap, and the bytes
  must decode as an image. Each image is normalized to a JPEG of at most 1024 px.
- The assistant thanks the user, announces the move to the design of the room, and asks **which
  elements they like and want to keep** (atmosphere, shapes, materials, colours, light, layout) and
  what to avoid, pointing out one or two things in each image.

**Phase 2: first concept image**

- Once the user says what they like, the assistant calls `generate_concept_image` with a complete
  visual brief and the numbers of the references to draw from.
- The result is saved as **version 1** in `concept_images` (base64) and shown to the user. The
  assistant then describes what it sees and asks what to keep or change.

**Phase 3: refining**

- Each piece of feedback produces a new version. The generator receives **past images to iterate
  on**: the latest version first (or `base_version` to go back to an earlier one), then the chosen
  references, at most `MAX_PAST_IMAGES` (the latest is always kept). The prompt says what changes and
  what must stay.
- The assistant generates only what the user asked for, one image per feedback, and says briefly what
  changed after each.

**Phase 4: validation**

- When the user seems happy, the assistant asks them to confirm that this version is the concept.
  Only after a clear yes, never in the same turn as the question, it calls `validate_concept`.
- The accepted image is copied into the main table: `session.concept_image` and
  `concept_design_validated = TRUE`. Generating a new image afterwards **reopens** the validation and
  clears the stored concept.

**The assistant sees the images.** Before every model call, the references and the latest concept
are read from the database and put in front of the conversation as image inputs, so the assistant
describes what is really there and sees a new image right after generating it. Images are not kept
in the graph state; the state only holds the progress (`ConceptDesign`: reference count, latest
version, validated flag, references revision).

**Tools:** `search_web_images`, `generate_concept_image`, `validate_concept` (one call at a time, each
generation builds on the previous one).

## Frontend

A Vue app (`frontend/`) that calls the API straight from the browser.

- **Chat** takes the whole width. The user types or dictates (the transcript goes into the box,
  it is not sent). Replies show the **images they produced, stacked in one column**: the 3 references
  when found, and each new concept version. References replaced by a newer search disappear from older
  messages instead of showing the wrong images.
- **Header** shows the current step (`Step 2/2 · Concept design`, from the API's `step`), the session
  id, the API health and a *New conversation* button (new session id, empty history).
- **Side tab** (right edge) opens a panel: step 1 shows what was gathered so far; step 2 shows the
  references and the latest concept with a *draft / validated* badge. It starts closed.

## API

| Route | Purpose |
|-------|---------|
| `POST /chat` | Run one turn. Body: `session_id` (optional, created if missing) and `messages` (whole history, oldest first, ends with a user message; empty for the welcome). Answer: `session_id`, `step`, `reply`, `information`, `concept`. |
| `GET /concept/{session_id}/references/{1..3}` | A reference image (bytes). |
| `GET /concept/{session_id}/images/{version}` | A generated concept image (bytes, never changes). |
| `GET /concept/{session_id}/validated` | The validated concept (404 until validated). |
| `POST /speech/transcribe` | Speech to text (OpenAI proxy). |
| `GET /health/live`, `/health/ready` | Probes. |

`concept` is `{ reference_count, latest_version, is_validated, references_revision }`: enough for a
client to build the image URLs above without receiving any base64 in the chat answer. Interactive docs
are at `/docs`.

## Data

| Table / column | Content |
|----------------|---------|
| `session` | one row per conversation: the step-1 fields and `is_validated`; `concept_image` (base64 of the validated concept) and `concept_design_validated` |
| `concept_reference_images` | the 3 web images of the session (`position`, base64, title, source and page URLs) |
| `concept_images` | every generated image (`version` 1, 2, 3…, base64, the prompt that made it) |

Init scripts are in `infrastructure/database/init/` and run **only when the database volume is first
created**. After pulling a new script, run `task docker:delete` then `task start` (this wipes the
data), or apply the script by hand with `psql`.

## Run it

Requirements: Docker, [Task](https://taskfile.dev), [uv](https://docs.astral.sh/uv/), Node.js, an
OpenAI API key.

```bash
cp backend/.env.backend.template backend/.env.backend                          # add OPENAI_API_KEY
cp infrastructure/.env.infrastructure.template infrastructure/.env.infrastructure
cp frontend/.env.frontend.template frontend/.env.frontend
uv sync

task start      # Langfuse, database, seed the prompts, backend, then the frontend
```

| Task | What it does |
|------|--------------|
| `task start` | Starts everything in order. The frontend stays in the foreground: Ctrl+C stops only the frontend. |
| `task restart` | Stops everything (data kept), then starts it all again. Prompts are re-seeded. |
| `task seed:prompts` | Publishes `infrastructure/langfuse/prompts/*.md` to Langfuse. Run it after editing a prompt file. |
| `task docker:stop` | Stops the frontend dev server and the Docker services, keeping data. |
| `task docker:delete` | Same, then deletes the containers and volumes: data is lost and every port is freed. |
| `task test` | Backend tests with a coverage report. Frontend: `npm test` in `frontend/`. |

Services: frontend <http://localhost:5173>, API <http://localhost:8888>, Langfuse
<http://localhost:3000>, Postgres `localhost:5432`.

**Configuration** lives in the three `.env.*` files (templates are committed, real files are
git-ignored). The ones worth knowing: `OPENAI_CHAT_MODEL` (the assistants, must accept images),
`GPT_COMPLETION_MODEL` (the vision model that ranks web images), `OPENAI_IMAGE_MODEL` and
`MAX_PAST_IMAGES` (concept generation), `LANGFUSE_PROMPT_LABEL` (which prompt version is served),
`CORS_ORIGINS` (must match the frontend port).

## Project layout

```
backend/
  api/                 FastAPI routes and schemas
  services/            chat, database, concept design, prompts, speech to text
  infra/               OpenAI, Postgres and Langfuse clients
  src/graph/
    graph.py           main graph: router and step chaining
    steps.py           Step enum and current_step()
    state.py           GraphState shared by every subgraph
    subgraphs/         one folder per step (information_gathering, concept_design)
    tools/             tools of the agents (gather_information, search_web_images,
                       generate_image, concept_design)
frontend/              Vue app
infrastructure/        Docker services, database init scripts, Langfuse prompts
```

**Adding a step:** add a value to `Step` and a rule in `current_step`, create its subgraph and prompt,
register it in `MainGraph.subgraphs` and `STEP_ROUTES`, and add its label in
`frontend/src/conversation.js` (`STEPS`).
