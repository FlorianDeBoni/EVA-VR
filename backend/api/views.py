import datetime

from django.http import StreamingHttpResponse, JsonResponse
from django.middleware.csrf import get_token
from pathlib import Path
import json
import re
from .core.utils.google_sheet import add_feedback_sheet, write_google_sheet
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import os
from dotenv import load_dotenv

from .core.azureLangchainAgent import (
    maybe_generate_image,
    send_chat_completion_stream,
)

def getCsrfToken(request):
    token = get_token(request)
    return JsonResponse({"csrfToken": token})

def getPrompts(request):
    if request.method != "GET":
        return JsonResponse({"error": "Invalid request method."}, status=405)
    try:
        current_dir = Path(__file__).parent
        prompt_path = current_dir / "core" / "prompts" / "gpt_prompt.md"

        with open(prompt_path, "r", encoding="utf-8") as f:
            system_prompt = f.read()
        return JsonResponse({"prompt": system_prompt}, status=200)
    
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

def chat(request):
    # --------------------------------------------------
    # Parse JSON body
    # --------------------------------------------------
    try:
        body = json.loads(request.body.decode("utf-8"))
        message = body.get("message")
        history = body.get("history", [])
        reference_image = body.get("reference_image", "")
    except json.JSONDecodeError:
        return StreamingHttpResponse(
            "data: " + json.dumps({
                "type": "error",
                "message": "Invalid JSON"
            }) + "\n\n",
            content_type="text/event-stream"
        )

    if not message:
        return StreamingHttpResponse(
            "data: " + json.dumps({
                "type": "error",
                "message": "No message provided"
            }) + "\n\n",
            content_type="text/event-stream"
        )

    # --------------------------------------------------
    # Load system prompt
    # --------------------------------------------------
    current_dir = Path(__file__).parent
    prompt_path = current_dir / "core" / "prompts" / "gpt_prompt.md"

    with open(prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read()

    # --------------------------------------------------
    # Build conversation history
    # IMPORTANT:
    # - NO placeholder instructions
    # - Images are handled as events, not text
    # --------------------------------------------------
    full_history = [
        {"role": "system", "content": system_prompt}
    ]

    for msg in history:
        if msg.get("content"):
            full_history.append({
                "role": msg["role"],
                "content": msg["content"]
            })

    # --------------------------------------------------
    # SSE event stream
    # --------------------------------------------------
    def event_stream():
        # 1️⃣ Let the agent handle tools + image decisions
        updated_history, reference_images, generated_images = (
            maybe_generate_image(full_history, reference_image=reference_image)
        )

        # 2️⃣ Send reference images chosen by the LLM (FIRST)
        for img in reference_images:
            payload = json.dumps({
                "type": "image",
                "id": img["id"],
                "url": img["url"],
                "source": img.get("source"),
                "title": img.get("title"),
            })
            print(f"Reference image: {img}")
            yield f"data: {payload}\n\n"

        # 3️⃣ Send AI-generated images (SECOND)
        for img in generated_images:
            payload = json.dumps({
                "type": "image",
                "id": img["id"],
                "b64": img["b64"],
            })
            print(f"Generated image")
            yield f"data: {payload}\n\n"

        def strip_image_urls(text: str) -> str:
            return re.sub(r'https?://\S+\.(jpg|jpeg|png|webp)\S*', '', text)

        progress_buffer = ""
        progress_resolved = False

        for chunk in send_chat_completion_stream(updated_history):
            clean = strip_image_urls(chunk)

            if not progress_resolved:
                progress_buffer += clean
                marker = re.match(r'^\s*\[\[SESSION_STEP:([1-5])\]\]\s*', progress_buffer)

                if marker:
                    step = int(marker.group(1))
                    progress_payload = json.dumps({"type": "progress", "step": step})
                    yield f"data: {progress_payload}\n\n"
                    clean = progress_buffer[marker.end():]
                    progress_buffer = ""
                    progress_resolved = True
                elif len(progress_buffer) < 32 and "\n" not in progress_buffer:
                    continue
                else:
                    clean = progress_buffer
                    progress_buffer = ""
                    progress_resolved = True

            if not clean:
                continue

            payload = json.dumps({
                "type": "text",
                "delta": clean
            })
            yield f"data: {payload}\n\n"

        if progress_buffer:
            payload = json.dumps({"type": "text", "delta": progress_buffer})
            yield f"data: {payload}\n\n"

        # 5️⃣ End of stream
        yield "data: [DONE]\n\n"

    return StreamingHttpResponse(
        event_stream(),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

def add_log(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method."}, status=405)
    try:
        load_dotenv()
        credentials_json = eval(os.environ["GOOGLE_CREDENTIALS"])
        
        creds = Credentials.from_service_account_info(credentials_json)
        service = build('sheets', 'v4', credentials=creds)
        
        sheet_id = os.environ["SHEET_ID"]
        body = json.loads(request.body.decode("utf-8"))
        values = [
            [
                datetime.datetime.now().isoformat(),
                body.get("user_id", ""),
                body.get("session_id", ""),
                body.get("input", ""),
                body.get("answer", ""),
                body.get("iteration", ""),
            ]
        ]
        write_google_sheet(service, sheet_id, "Logs", {"values": values})

        return JsonResponse({"message": "Log entry added successfully."}, status=200)
    
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
def add_feedback(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method."}, status=405)
    try:
        load_dotenv()
        credentials_json = eval(os.environ["GOOGLE_CREDENTIALS"])
        
        creds = Credentials.from_service_account_info(credentials_json)
        service = build('sheets', 'v4', credentials=creds)
        
        sheet_id = os.environ["SHEET_ID"]
        body = json.loads(request.body.decode("utf-8"))
        print(f"Received feedback: session_id={body.get('session_id', '')}, iteration={body.get('iteration', '')}, feedback={body.get('feedback', '')}")
        add_feedback_sheet(
            service, 
            sheet_id, 
            "Logs", 
            session_id=body.get('session_id', ''),
            iteration=body.get('iteration', ''),
            feedback=body.get('feedback', ''),
        )

        return JsonResponse({"message": "Feedback entry added successfully."}, status=200)
    
    except json.JSONDecodeError:
        print("Invalid JSON received in add_feedback")
        return JsonResponse({"error": "Invalid JSON."}, status=400)
    except Exception as e:
        print(f"Error adding feedback: {e}")
        return JsonResponse({"error": str(e)}, status=500)
    
def update_prompt(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method."}, status=405)
    try:
        body = json.loads(request.body.decode("utf-8"))
        new_prompt = body.get("prompt")
        if not new_prompt:
            return JsonResponse({"error": "No prompt provided."}, status=400)

        current_dir = Path(__file__).parent
        prompt_path = current_dir / "core" / "prompts" / "gpt_prompt.md"

        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(new_prompt)

        return JsonResponse({"message": "Prompt updated successfully."}, status=200)
    
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
