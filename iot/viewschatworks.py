import re
import requests
from collections import defaultdict
from django.http import JsonResponse
from .models import ChatworkMessage
from datetime import datetime
from pytz import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required

CHATWORK_TOKEN = '91460d38143a3128bfad65e4b2e9a993'
ROOM_IDS = ['264687873', '292318431']  # Danh sách các ROOM_ID bạn muốn lấy

ROOM_ID = '407707641'  # Giữ lại để không ảnh hưởng logic cũ

def chatwork_latest(request):
    jp_tz = timezone('Asia/Tokyo')
    msg = ChatworkMessage.objects.only('message', 'sender', 'time', 'message_id').order_by('-time').first()
    if not msg:
        return JsonResponse({"message": ""})
    jp_time = msg.time.astimezone(jp_tz)
    return JsonResponse({
        "message": msg.message,
        "sender": msg.sender,
        "time": jp_time.strftime("%Y-%m-%d %H:%M"),
        "message_id": msg.message_id,
    })

def chatwork_list(request):
    headers = {'X-ChatWorkToken': CHATWORK_TOKEN}
    url = f'https://api.chatwork.com/v2/rooms/{ROOM_ID}/messages'
    res = requests.get(url, headers=headers)
    messages = []
    if res.ok:
        for msg in res.json():
            body = msg.get('body', '')
            messages.append({
                'message': body,
                'time': msg.get('send_time', ''),
            })
    return JsonResponse({'messages': messages})

def chatwork_latest_from_db(request):
    msg = ChatworkMessage.objects.only('message', 'sender', 'time').order_by('-time').first()
    if not msg:
        return JsonResponse({"message": ""})
    return JsonResponse({
        "message": msg.message,
        "sender": msg.sender,
        "time": msg.time.strftime("%Y-%m-%d %H:%M"),
    })

def chatwork_list_from_db(request):
    messages = ChatworkMessage.objects.only('message', 'sender', 'time').order_by('-time')[:20]
    return JsonResponse({
        "messages": [
            {
                "message": m.message,
                "sender": m.sender,
                "time": m.time.strftime("%Y-%m-%d %H:%M"),
            } for m in messages
        ]
    })

def extract_text_only(text):
    # Loại bỏ đoạn [info][title][dtext:file_uploaded]...[/info] (thường là file/ảnh)
    return re.sub(r'\[info\]\[title\]\[dtext:file_uploaded\].*?\[/info\]', '', text, flags=re.DOTALL).strip()

def sync_chatwork_to_db():
    headers = {'X-ChatWorkToken': CHATWORK_TOKEN}
    # Lấy tin nhắn từ nhiều phòng
    for room_id in ROOM_IDS:
        url = f'https://api.chatwork.com/v2/rooms/{room_id}/messages'
        res = requests.get(url, headers=headers)
        if res.ok:
            for msg in res.json():
                body = extract_text_only(msg.get('body', ''))
                message_id = str(msg.get('message_id', ''))
                if not ChatworkMessage.objects.filter(message_id=message_id).exists():
                    ChatworkMessage.objects.create(
                        message_id=message_id,
                        message=body,
                        sender=msg.get('account', {}).get('name', ''),
                        time=datetime.fromtimestamp(msg.get('send_time', 0)),
                    )
        else:
            print(f"❌ Failed to sync messages from Chatwork API room {room_id}")

def chatwork_grouped_by_date(request):
    jp_tz = timezone('Asia/Tokyo')
    messages = ChatworkMessage.objects.only('message', 'sender', 'time', 'message_id').order_by('-time')[:200]
    groups = defaultdict(list)
    for m in messages:
        jp_time = m.time.astimezone(jp_tz)
        date = jp_time.strftime("%Y-%m-%d")
        groups[date].append({
            "message_id": m.message_id,
            "message": extract_text_only(m.message),
            "sender": m.sender,
            "time": jp_time.strftime("%Y-%m-%d %H:%M"),
        })
    return JsonResponse({"groups": dict(groups)})

@csrf_exempt
@require_POST
@login_required
def chatwork_delete_message(request):
    if not request.user.is_superuser:
        return JsonResponse({"success": False, "error": "権限がありません"}, status=403)
    import json
    data = json.loads(request.body)
    message_ids = data.get("message_ids")
    if message_ids:
        ChatworkMessage.objects.filter(message_id__in=message_ids).delete()
        return JsonResponse({"success": True})
    message_id = data.get("message_id")
    if message_id:
        msg = get_object_or_404(ChatworkMessage, message_id=message_id)
        msg.delete()
        return JsonResponse({"success": True})
    return JsonResponse({"success": False, "error": "Missing message_id"}, status=400)


