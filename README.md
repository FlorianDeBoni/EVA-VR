# EVA-VR

A chatbot-led design workshop whose goal is to **imagine and design a room that boosts creativity**.
The user talks to an assistant; the workshop moves through steps, and each step has its own
assistant, its own prompt and its own tools. The assistant also speaks to the user through
images (references, generated pictures), and the workshop ends with a final picture of the room.

| Step | Name | Ends when | Stored in the database |
|------|------|-----------|------------------------|
| 1 | Information gathering | the user confirms the summary of their answers | the `session` row (`is_validated`) |
| 2 | Concept design | the user accepts a generated concept image | `session.concept_image` + `concept_design_validated` |
| 3 | Spatial design | the user accepts a picture of the spatial organization (spaces and how they relate) | `session.spatial_design` + `spatial_image` + `spatial_design_validated` |
| 4 | Detailed design | the user accepts the final picture, with the furniture, shapes, materials and colors | `session.detailed_design` + `final_image` + `detailed_design_validated` |

Everything below describes what each step does and why. For setup, jump to [Run it](#run-it).

## How a conversation works

- **The API keeps no history.** The browser owns the conversation: every `POST /chat` carries the
  whole message list (texts only) and the `session_id`. Everything that must survive between turns
  (gathered information, images, validation flags) is in the database.
- **One graph, one subgraph per step.** The main graph (LangGraph) is a router in front of the
  subgraphs. Each subgraph is a small agent: *model ⇄ tools*, repeated until the model answers
  without calling a tool. All of them share the same state (`GraphState`).
- **The current step is derived, never stored.** `current_step(state)` (`backend/src/graph/steps.py`)
  gives step 1 until the information is validated, step 2 until the concept is validated, step 3
  after. The router and the API answer
  (`step`) both use it, so they cannot disagree.
- **Steps chain inside one turn.** A step's subgraph ends right after its validation tool succeeds
  (it writes nothing more), and the graph continues straight into the next step, which speaks next.
  The `step` in that very answer is already the new one. The last step has no next step, so its
  assistant does say goodbye.
- **Prompts live in Langfuse**, one markdown file per step in `infrastructure/langfuse/prompts/`,
  published by `task seed:prompts`. Edit them in Langfuse to tune the assistants without redeploying.

```
START ──router (by current step)──► gather_information ─┐
                                    concept_design ◄────┤ each subgraph, once its step is
                                    spatial_design ◄────┤ validated, hands over to the next
                                    detailed_design ◄───┘ one in the same turn; otherwise END
                                          │
                                          ▼
                                         END
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
light). Details such as furniture, equipment or dimensions are acknowledged and deferred to later
steps. **Prompt:** `concept_design`. **Code:** `backend/src/graph/subgraphs/concept_design/`.

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

- Once the user says what they like, the assistant calls `generate_image` with a complete
  visual brief and the numbers of the references to draw from.
- The result is saved as **version 1** in `concept_images` (base64) and shown to the user. The
  assistant then describes what it sees and asks what to keep or change.

**Phase 3: refining**

- Each piece of feedback produces a new version. The generator receives **past images to iterate
  on**: the latest version first (or `base_version` to go back to an earlier one), then the chosen
  references. Every input image makes generating slower, so a new image is built from **at most 3
  input images, however many times the user iterates** (`MAX_INPUT_IMAGES`; `MAX_PAST_IMAGES` can lower
  that limit, never raise it). Older versions are never sent: only the latest one, so the cost of an
  iteration does not grow. The prompt says what changes and what must stay, and asks the assistant not
  to pass the references again after the first image.
- The assistant generates only what the user asked for, one image per feedback, and says briefly what
  changed after each.

**Phase 4: validation**

- Validation is deliberately light: the assistant never makes the user confirm the same thing twice.
  When the user clearly accepts the version or asks to move on ("perfect, that's the one", "let's
  continue"), it calls `validate_concept` right away, with no summary and no extra question. When the
  user only reacts mildly ("nice", "better"), it asks one short closing question, and any answer that
  accepts validates immediately. While the user keeps asking for changes, it does not bring up
  validation at all.
- The accepted image is copied into the main table: `session.concept_image` and
  `concept_design_validated = TRUE`. The step ends there and writes nothing more: step 3 starts in
  the same turn.

**The assistant sees the images.** Before every model call, the references and the latest concept
are read from the database and put in front of the conversation as image inputs, so the assistant
describes what is really there and sees a new image right after generating it. Images are not kept
in the graph state; the state only holds the progress (`ConceptDesign`: reference count, latest
version, validated flag, references revision).

**Tools:** `search_web_images`, `generate_image`, `validate_concept` (one call at a time, each
generation builds on the previous one).

## Step 3: Spatial design

**Assistant:** translates the validated concept into a **spatial organization**: which spaces or areas
the room needs to carry out the task, and how those spaces relate and interact. The step ends with a
**new picture**, a refined version of the concept that shows this organization, which the user must
accept before the workshop moves on. It does **not** talk about furniture, equipment, materials,
colours or exact dimensions (relative sizes and capacities are fine). No web search.
**Prompt:** `spatial_design`. **Code:** `backend/src/graph/subgraphs/spatial_design/`.

**What it produces:** a `SpatialDesign` and a picture of it.

| Part | Content |
|------|---------|
| `spaces` | each space has a `name`, its `purpose` for the task, its `activities`, a `capacity` (people at once) and a relative `size` |
| `relationships` | each links two spaces by name with a `type` and a short `description` of how they interact |
| picture | an image that shows the organization in the style, mood and materials of the validated concept |

Relationship types: `adjacent` (next to each other, clear boundary), `open_connection` (one
continuous volume), `visual_link` (one sees the other), `separated` (kept apart on purpose: noise,
privacy), `circulation` (people move from one to the other).

**Behavior**

1. **Starting point.** The validated concept image is read from the database and given to the model
   as an image input on every call, along with the step-1 information and the current draft.
2. **First draft.** With no draft yet, the assistant's first action is to record one
   (`update_spatial_design`, usually 3 to 6 spaces and the obvious relationships) from the concept and
   the information. It then thanks the user, says how it reads the concept, presents the draft in a
   few lines and asks its first question.
3. **Refining by questions.** One question at a time, two at most, always about what is unclear or
   missing: the stages of the task and which need their own space, how many people per space, what
   needs quiet or privacy, what should be connected, visible or separated, how people move, which
   spaces matter most. Each question starts from what is already known and may come with a concrete
   suggestion. It stays faithful to the concept image and says so when the user's wish clashes with it.
4. **Recording comes first.** Every change (space added, renamed, removed; purpose, capacity, size or
   relationship changed) is saved with `update_spatial_design` before the assistant replies. Each call
   sends the complete list of spaces and/or of relationships (a list replaces the previous one). The
   tool refuses inconsistent designs: duplicate space names, a relationship naming an unknown space,
   a space linked to itself, or removing a space that a saved relationship still uses.
5. **The picture.** When each main activity has a space, the important relationships are covered and the
   user has nothing more to change, the assistant says it is going to draw the organization and calls
   `generate_image` with a visual brief: each space, where it is, its relative size and how it connects
   to the others, in the style of the validated concept, one readable view, no text and no detailed
   furniture. The picture starts from the validated concept. It is shown to the user and the assistant
   describes how it shows the organization.
6. **Refining the picture.** Feedback on the picture either changes the organization (the assistant
   records it first, then draws again) or only the drawing. Each new picture iterates on the latest one
   (or on `base_version`) and keeps the validated concept as a style anchor: two input images, within
   the same limit of 3 as step 2. The saved organization and the picture must always agree.
7. **Validation.** Light, as in step 2: a clear acceptance or "let's move on" validates right away
   (`validate_spatial_design`, with no summary turn); a mild reaction gets one closing question with a
   one-sentence recap of the organization, and any accepting answer validates immediately. The picture
   and the organization are validated together. The tool refuses with fewer than 2 spaces, without
   any relationship, without a picture, or **if the organization was changed after that picture**: the
   stored picture always matches the stored organization. In that case the assistant draws the current
   organization and asks once whether this new picture is right, since the user has not seen it. After
   a successful validation the step ends and writes nothing more: step 4 starts in the same turn.

**Storage, like step 2:** the working draft is one row of `spatial_design_drafts` (JSON), replaced on
every change. The pictures are rows of `concept_images` with `step = 3`; their version numbers keep
counting after those of step 2. Only the validated result is copied into the `session` row:
`spatial_design`, `spatial_image` and `spatial_design_validated = TRUE`. Changing the draft or drawing
a new picture afterwards reopens the validation and clears that copy. Step 2's validated concept is
never touched by step 3.

**Tools:** `update_spatial_design`, `generate_image` (the same tool as step 2), `validate_spatial_design`
(one call at a time: each update rewrites the whole draft, each picture builds on the previous one).

## Step 4: Detailed design

**Assistant:** the last step. It starts from the picture the user validated in step 3 and keeps its
layout: the spaces, their positions, their sizes and the point of view stay as they are, and only
**minor details** change. The details are the **furniture** the creative task needs, then shapes,
materials, colors, lighting and accessories. The step ends with a **final picture**: the spatial
picture with all these details, an AI-generated image that is the final result of the workshop.
**Prompt:** `detailed_design`. **Code:** `backend/src/graph/subgraphs/detailed_design/`.

**What it produces:** a `DetailedDesign` and a picture of it.

| Part | Content |
|------|---------|
| `details` | each has a `name`, a `category` (`furniture`, `shape`, `material`, `color`, `lighting`, `accessory`), a `description` (shape, material, color, why the task needs it), an optional `space` (a space of step 3, or none for the whole room) and, for furniture, a `quantity` |
| picture | the validated spatial picture, with these details, in the same layout |

**Behavior**, in the same shape as step 3:

1. **Starting point.** The validated spatial picture is given to the model as an image input on every
   call, with the step-1 information, the validated spaces and the current draft.
2. **First draft.** With no detail yet, the assistant's first action is to record one
   (`update_detailed_design`): the furniture each space needs to do its part of the task, plus a few
   room-wide details (palette, main materials, lighting). It then thanks the user, says this is the last
   step, presents the draft in a few lines and asks its first question.
3. **Refining by questions.** One at a time, two at most: how people work in each space and so what
   furniture, how many and how big; what must be movable; the tools within reach; the feel (soft or
   sharp shapes, warm or cool materials, energizing colors); the light; the small touches. If the user
   asks to move, resize, add or remove a space, the assistant says the organization was validated in the
   previous step and brings the conversation back to the details.
4. **Recording comes first.** Every change is saved with `update_detailed_design` before the reply. Each
   call sends the complete list of details. The tool refuses a detail whose space does not exist in step
   3 and duplicates (same name in the same space).
5. **The final picture.** When the furniture is settled and the shapes, materials and colors are clear,
   the assistant draws with `generate_image`: exactly the same room as the validated picture (same layout,
   proportions, point of view), with the details listed space by space. The picture starts from the
   validated spatial picture, so the layout is carried by the image itself.
6. **Refining the picture.** Same as step 3: feedback may change the details (recorded first) or only the
   drawing; each new picture iterates on the latest one and keeps the validated spatial picture as a
   layout anchor, within the limit of 3 input images.
7. **Validation, in two ways that follow the same rules.** The user can say it in the chat: light, as in
   steps 2 and 3, handled by `validate_detailed_design`. Or they can click the **Validate final
   version** button, which accepts the latest picture in one click with no round trip through the
   chat (the assistant tells them about the button when it shows the first picture). Both refuse
   without any piece of furniture, without a picture, or **if the details changed after that picture**
   (`validation_problem` in `tools/detailed_design/rules.py`, plus the check in the database). After
   the chat validation the assistant, as it is the last step, thanks the user, says that this is the
   final version of the room and that the **Go to VR** button now shows it. After a click it says the
   same in its next reply, without asking anything about validation. A change asked afterwards makes a
   new picture, which reopens the validation.

**Storage, like steps 2 and 3:** the working draft is one row of `detailed_design_drafts` (JSON). The
pictures are rows of `concept_images` with `step = 4`, counting on from step 3's. Only the validated
result is copied into the `session` row: `detailed_design`, `final_image` and
`detailed_design_validated = TRUE`. Changing the draft or drawing a new picture afterwards reopens
the validation and clears that copy, and never touches steps 2 and 3.

**Tools:** `update_detailed_design`, `generate_image`, `validate_detailed_design`.

## Frontend

A Vue app (`frontend/`) that calls the API straight from the browser.

- **Chat** takes the whole width. The user types or dictates (the transcript goes into the box,
  it is not sent). Replies show the **images they produced, stacked in one column**: the 3 references
  when found, and each new concept version. References replaced by a newer search disappear from older
  messages instead of showing the wrong images.
- **Header** shows the current step (`Step 4/4 · Detailed design`, from the API's `step`), the session
  id, the API health and a *New conversation* button (new session id, empty history).
- **Validate final version** button, in the header, appears in step 4 while there is a picture that was
  not accepted yet. One click calls `POST /detailed-design/{session_id}/validate`; if the server
  refuses (no furniture, details changed after the picture), the reason is shown next to the button.
- **Go to VR** button, in the header, replaces it once the final design is validated, by the button or
  by the assistant (`detailed_design.is_validated`). It opens `vr.html?session=<id>` in a new tab: a separate page
  (`frontend/vr.html`) that shows the final picture alone, filling the window without cropping it.
  It asks the API for `GET /concept/{session_id}/final`, and says so if there is no final picture yet.
- **Side tab** (right edge) opens a panel for the current step: step 1 shows what was gathered so far;
  step 2 the references and the latest concept with a *draft / validated* badge; step 3 the refined picture, the
  validated concept it starts from, the spaces and their relationships, with the same badge; step 4 the
  latest picture, the spatial picture it starts from and the details grouped by category (*draft / final*).
  It starts closed.

## API

| Route | Purpose |
|-------|---------|
| `POST /chat` | Run one turn. Body: `session_id` (optional, created if missing) and `messages` (whole history, oldest first, ends with a user message; empty for the welcome). Answer: `session_id`, `step`, `reply`, `information`, `concept`, `spatial_design`, `detailed_design`. |
| `GET /concept/{session_id}/references/{1..3}` | A reference image (bytes). |
| `GET /concept/{session_id}/images/{version}` | A generated concept image (bytes, never changes). |
| `GET /concept/{session_id}/validated` | The concept validated in step 2 (404 until validated). |
| `GET /concept/{session_id}/spatial` | The spatial picture validated in step 3 (404 until validated). |
| `POST /detailed-design/{session_id}/validate` | Accepts a picture of step 4 as the final design without the chat (body `{version}`, default the latest). Same rules as the assistant's tool; `409` with the reason when it cannot be validated yet. Returns the validated `detailed_design`. |
| `GET /concept/{session_id}/final` | The final picture validated in step 4, shown by the VR page (404 until validated). |
| `POST /speech/transcribe` | Speech to text (OpenAI proxy). |
| `GET /health/live`, `/health/ready` | Probes. |

`concept` is `{ reference_count, latest_version, is_validated, references_revision }`: enough for a
client to build the image URLs above without receiving any base64 in the chat answer.
`spatial_design` is `{ spaces, relationships, latest_image_version, is_validated }` (empty lists until
the assistant drafts it; the picture is `GET /concept/{session_id}/images/{latest_image_version}`). Interactive docs are at `/docs`.

## Data

| Table / column | Content |
|----------------|---------|
| `session` | one row per conversation: the step-1 fields and `is_validated`; `concept_image` (base64 of the validated concept) and `concept_design_validated` |
| `concept_reference_images` | the 3 web images of the session (`position`, base64, title, source and page URLs) |
| `concept_images` | every generated image of steps 2, 3 and 4 (`version` 1, 2, 3… counting across both, `step`, base64, the prompt that made it) |
| `session.spatial_design` / `spatial_image` / `spatial_design_validated` | the validated spatial design (JSON), its picture (base64) and the flag |
| `spatial_design_drafts` | the working spatial design of the session, one row, replaced on every change |
| `session.detailed_design` / `final_image` / `detailed_design_validated` | the validated detailed design (JSON), the final picture (base64) and the flag |
| `detailed_design_drafts` | the working detailed design of the session, one row, replaced on every change |

Init scripts are in `infrastructure/database/init/`. Docker only runs them when the database volume is
first created, so `task dev:database` (run by `task start` and `task restart`) also applies them all to
the running database with `task migrate:database`. The scripts are written to be safe to run again
(`IF NOT EXISTS`, `CREATE OR REPLACE`), so a new script reaches an existing database without losing data.
Add new schema changes as a new numbered script written the same way.

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
| `task migrate:database` | Applies the database init scripts to the running database (also done by `start` and `restart`). |
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
    subgraphs/         one folder per step (information_gathering, concept_design,
                       spatial_design, detailed_design)
    tools/             tools of the agents (gather_information, search_web_images,
                       generate_image, concept_design, spatial_design, detailed_design)
frontend/              Vue app: index.html (the workshop) and vr.html (the final picture, full screen)
infrastructure/        Docker services, database init scripts, Langfuse prompts
```

**Adding a step:** add a value to `Step` and a rule in `current_step`, create its subgraph and prompt,
register it in `MainGraph.subgraphs` and `STEP_ROUTES`, and add its label in
`frontend/src/conversation.js` (`STEPS`) and the panel labels in `frontend/src/App.vue`. If it
follows a step that is currently the last one, end that step's subgraph right after its validation tool
(see `after_tools` in the concept design graph) so the new step speaks next.
