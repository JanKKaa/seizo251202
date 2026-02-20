from django.contrib.auth.models import User
from phe_duyet.models import Message, Document, Approval
from trang_chu.utils.japan_events import get_japan_event

def unread_messages_count(request):
    if request.user.is_authenticated:
        unread_count = Message.objects.filter(recipient=request.user, read=False).count()
    else:
        unread_count = 0
    return {'unread_messages_count': unread_count}



def approve_button_count(request):
    if request.user.is_authenticated:
        approve_count = Approval.objects.filter(
            document__recipient=request.user, 
            approved=False, 
            rejected=False
        ).count()
    else:
        approve_count = 0
    return {'approve_button_count': approve_count}

def japan_event(request):
    return {'japan_event': get_japan_event()}