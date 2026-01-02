from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags

def send_whatsapp_message(phone_number, message_text):
    """
    Mock WhatsApp sender.
    """
    print(f"\n==========================================")
    print(f"📲 [WHATSAPP MOCK] To: {phone_number}")
    print(f"📩 Message: {message_text}")
    print(f"==========================================\n")

def send_welcome_notification(user):
    """
    Sends HTML Welcome Email and WhatsApp.
    """
    subject = "Welcome into the family of Recgetup Music! 🎤"
    
    # Render HTML content
    context = {
        'user': user,
        'domain': '127.0.0.1:9999' # Hardcoded for local dev, usually passed dynamically
    }
    html_message = render_to_string('quizzes/emails/welcome_email.html', context)
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(subject, plain_message, settings.EMAIL_HOST_USER, [user.email], html_message=html_message)
        print(f"✅ Welcome Email Sent to {user.email}")
    except Exception as e:
        print(f"❌ Welcome Email Failed: {e}")

    # WhatsApp
    if hasattr(user, 'profile') and user.profile.phone_number:
        wa_msg = f"Welcome {user.first_name}! 🎤 Thanks for joining Recgetup Music. Check your dashboard for upcoming classes."
        send_whatsapp_message(user.profile.phone_number, wa_msg)

def send_payment_success_notification(user, package_name, amount, transaction_id):
    """
    Sends HTML Receipt and WhatsApp.
    """
    subject = f"Payment Receipt: {package_name} ✅"
    
    context = {
        'user': user,
        'package_name': package_name,
        'amount': amount,
        'transaction_id': transaction_id,
        'domain': '127.0.0.1:9999'
    }
    html_message = render_to_string('quizzes/emails/payment_email.html', context)
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(subject, plain_message, settings.EMAIL_HOST_USER, [user.email], html_message=html_message)
        print(f"✅ Payment Email Sent to {user.email}")
    except Exception as e:
        print(f"❌ Payment Email Failed: {e}")

    # WhatsApp
    if hasattr(user, 'profile') and user.profile.phone_number:
        wa_msg = f"✅ Payment Received: ₹{amount} for {package_name}. Transaction ID: {transaction_id}"
        send_whatsapp_message(user.profile.phone_number, wa_msg)
