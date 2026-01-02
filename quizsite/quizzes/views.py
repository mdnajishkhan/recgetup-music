from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import models
from django.db.models import Q

# Import Updated Models
from .models import ScheduledClass, ClassPackage, UserSubscription, PaymentHistory
from .forms import UserRegistrationForm, UserLoginForm, EmailValidationPasswordResetForm, CustomSetPasswordForm, UserUpdateForm, ProfileUpdateForm
from .notifications import send_welcome_notification, send_payment_success_notification

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.contrib.auth.models import User
from django.contrib.auth import views as auth_views
from django.utils.html import strip_tags
from django.urls import reverse_lazy
from django.views.decorators.clickjacking import xframe_options_sameorigin

# 🏠 Home page (Public Access / Dashboard)
def home(request):
    if request.user.is_authenticated:
        user = request.user
        
        # 1. 💳 Active Subscription
        active_sub = UserSubscription.objects.filter(user=user, is_active=True).first()
        if active_sub and active_sub.is_expired:
            active_sub.is_active = False
            active_sub.save()
            active_sub = None
            
        # 2. 📅 Upcoming Classes (Filtered by Package)
        # Default: Show only Universal classes (packages=None)
        access_filter = Q(packages=None)
        
        # If user has an active package, include classes for that package
        if active_sub and active_sub.package:
            access_filter |= Q(packages=active_sub.package)
            
        upcoming_classes = ScheduledClass.objects.filter(access_filter, start_time__gte=timezone.now()).distinct().order_by('start_time')[:1]

        context = {
            'upcoming_classes': upcoming_classes,
            'active_sub': active_sub,
        }
        return render(request, 'quizzes/home.html', context)
    
    # Guest User Land Page
    return render(request, 'quizzes/home.html')

# 📅 Schedule View
@login_required
def schedule_view(request):
    # 1. Get User's Package
    active_sub = UserSubscription.objects.filter(user=request.user, is_active=True).first()
    
    # 2. Define Access Filter
    # Show Universal Layouts (packages is Empty)
    access_filter = Q(packages=None)
    
    if active_sub and not active_sub.is_expired and active_sub.package:
        # OR Show classes for their specific package
        access_filter |= Q(packages=active_sub.package)
    
    # 3. Filter Classes
    all_classes = ScheduledClass.objects.filter(access_filter, start_time__gte=timezone.now()).distinct().order_by('start_time')
    return render(request, 'quizzes/schedule.html', {'classes': all_classes})

# 💳 Plan / Packages View
def packages_view(request):
    packages = ClassPackage.objects.filter(is_active=True)
    return render(request, 'quizzes/packages.html', {'packages': packages})

import razorpay
from django.urls import reverse

# 💸 Pay for Package (Razorpay)
@login_required
def payment_initiate(request, package_id):
    package = get_object_or_404(ClassPackage, id=package_id)
    
    # Initialize Razorpay Client
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    
    # Create Razorpay Order
    payment_amount = int(package.price * 100) # Amount in paise
    payment_currency = 'INR'
    
    order_data = {
        'amount': payment_amount,
        'currency': payment_currency,
        'payment_capture': '1', # Auto capture
        'notes': {
            'package_id': package.id,
            'user_id': request.user.id
        }
    }
    
    try:
        order = client.order.create(data=order_data)
        
        # Create Pending Payment Record
        PaymentHistory.objects.create(
            user=request.user,
            package=package,
            amount=package.price,
            transaction_id=order['id'], # Save Order ID here
            status='PENDING'
        )
        
    except Exception as e:
        messages.error(request, f"Payment Gateway Error: {str(e)}")
        return redirect('packages')
        
    context = {
        'package': package,
        'order': order,
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'callback_url': request.build_absolute_uri(reverse('payment_verify')),
        'user': request.user
    }
    
    return render(request, 'quizzes/payment_confirm.html', context)

@csrf_exempt
def payment_verify(request):
    if request.method == "POST":
        try:
            payment_id = request.POST.get('razorpay_payment_id', '')
            order_id = request.POST.get('razorpay_order_id', '')
            signature = request.POST.get('razorpay_signature', '')
            
            print(f"DEBUG: Verifying Payment - Order: {order_id}, Payment: {payment_id}")

            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            
            # Verify Signature
            params_dict = {
                'razorpay_order_id': order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            }
            
            # This raises Error if verification fails
            client.utility.verify_payment_signature(params_dict)
            
            # --- SUCCESS ---
            # 1. Update Payment History
            # Use filter().first() to avoid crash if not found immediately (though it should exist)
            payment = PaymentHistory.objects.filter(transaction_id=order_id).first()
            
            if not payment:
                print("DEBUG: Payment Record Not Found in DB")
                messages.error(request, f"System Error: Payment record for Order {order_id} not found.")
                return redirect('packages')

            payment.status = 'SUCCESS'
            payment.save()
            print(f"DEBUG: Payment {payment.id} marked SUCCESS")
            
            # 2. Activate/Update Subscription
            duration_days = payment.package.duration_months * 30
            end_date = timezone.now() + timezone.timedelta(days=duration_days)
            
            # Use update_or_create to handle the OneToOneField constraint
            # This fixes the "Duplicate entry" error
            UserSubscription.objects.update_or_create(
                user=payment.user,
                defaults={
                    'package': payment.package,
                    'end_date': end_date,
                    'is_active': True
                }
            )
            print(f"DEBUG: Subscription Activated for {payment.user.username}")
            
            # 💸 Send Payment Notifications
            send_payment_success_notification(
                user=payment.user,
                package_name=payment.package.name,
                amount=payment.amount,
                transaction_id=order_id
            )
            
            messages.success(request, f"Payment Successful! You are subscribed to {payment.package.name}.")
            return redirect('home')

        except razorpay.errors.SignatureVerificationError as e:
            print(f"DEBUG: Signature Error: {e}")
            messages.error(request, "Payment Failed: Signature Verification Failed.")
            return redirect('packages')
        except Exception as e:
            print(f"DEBUG: General Error: {e}")
            messages.error(request, f"An error occurred during verification: {str(e)}")
            return redirect('packages')
    
    return redirect('packages')

# 🧾 Payment History
@login_required
def payment_history(request):
    history = PaymentHistory.objects.filter(user=request.user).order_by('-payment_date')
    return render(request, 'quizzes/payment_history.html', {'history': history})


# 👤 User Registration

def category_detail(request, slug):
    content = {
        'indian-classical': {
            'title': 'Indian Classical Vocals',
            'subtitle': 'Master the Ancient Art of Raga & Riyaz',
            'description': 'Embark on a spiritual journey through the 7 notes (Swara). From basic Alankars to complex Raag improvisations, learn the foundation of all Indian music.',
            'image': 'quizzes/images/indian_classical_banner.png',
            'color': 'amber',
            'icon': '🕉️',
            'curriculum': [
                {'title': 'Swara & Shruti', 'desc': 'Perfecting the 22 microtones of Indian music.'},
                {'title': 'Raag Mastery', 'desc': 'Deep dive into Raag Yaman, Bhairav, and more.'},
                {'title': 'Taal & Rhythm', 'desc': 'Mastering Tabla beats (Teentaal, Dadra).'},
                {'title': 'Voice Culture', 'desc': 'Gamma, Meend, and Murki techniques.'}
            ],
            'mentor': 'Pt. Ravi Shankar Style',
            'quote': "Music is not just art, it is yoga for the soul."
        },
        'western-pop': {
            'title': 'Western Pop Vocals',
            'subtitle': 'Own the Stage with Power & Style',
            'description': 'Unlock your full vocal range, master breath control, and learn to belt like a star. This course is designed for modern performers.',
            'image': 'quizzes/images/western_pop_banner.png',
            'color': 'purple',
            'icon': '🎤',
            'curriculum': [
                {'title': 'Breath Control', 'desc': 'Diaphragmatic support for long notes.'},
                {'title': 'Belting & Mix', 'desc': 'Hitting high notes without strain.'},
                {'title': 'Riffs & Runs', 'desc': 'Agility exercises for modern pop style.'},
                {'title': 'Stage Presence', 'desc': 'Mic technique and performance confidence.'}
            ],
            'mentor': 'Pop Icon Style',
            'quote': "Don't just sing the song, perform it."
        },
        'bollywood-sufi': {
            'title': 'Bollywood & Sufi',
            'subtitle': 'Sing with Soul, Emotion & Texture',
            'description': 'Bridging the gap between classical technique and commercial playback singing. Learn the "Harkat" and expressions that define Bollywood hits.',
            'image': 'quizzes/images/bollywood_sufi_banner.png',
            'color': 'red',
            'icon': '🎵',
            'curriculum': [
                {'title': 'Playback Techniques', 'desc': 'Singing for the microphone studio recording.'},
                {'title': 'Urdu Pronunciation', 'desc': 'Perfecting Talaffuz for Sufi Kalam.'},
                {'title': 'Emotional Expression', 'desc': 'Acting through your voice.'},
                {'title': 'Versatility', 'desc': 'Switching between romantic and upbeat tracks.'}
            ],
            'mentor': 'Sufi Master Style',
            'quote': "A voice that doesn't touch the heart is just noise."
        }
    }
    
    context = content.get(slug)
    if not context:
        return redirect('home')
        
    return render(request, 'quizzes/category_detail.html', context)

def register(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False  # Deactivate until verified
            user.set_password(form.cleaned_data['password'])
            user.save()
            
            # Explicitly save phone number to profile
            # (since form.save(commit=False) skips the custom save method logic)
            if hasattr(user, 'profile'):
                user.profile.phone_number = form.cleaned_data.get('phone_number')
                user.profile.save()

            # Send Verification Email
            current_site = get_current_site(request)
            mail_subject = 'Activate your account.'
            html_message = render_to_string('quizzes/acc_active_email.html', {
                'user': user,
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user),
            })
            plain_message = strip_tags(html_message)
            to_email = form.cleaned_data.get('email')
            
            # Use fail_silently=False to surface errors during dev, but True in prod usually
            send_mail(
                subject=mail_subject,
                message=plain_message,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[to_email],
                html_message=html_message
            )
            
            messages.success(request, "Please check your email to verify your account.")
            return redirect('login')
    else:
        form = UserRegistrationForm()
    return render(request, 'quizzes/register.html', {'form': form})


# 🔓 Activate Account
def activate(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except(TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        
        # 🎉 Send Welcome Notifications
        send_welcome_notification(user)
        
        messages.success(request, "✅ Email verified successfully! You can now login.")
        return redirect('login')
    else:
        messages.error(request, "❌ Activation link is invalid or has expired!")
        return redirect('register')


# -------------------------------------------------------------------
#  PROFILE VIEW
# -------------------------------------------------------------------
@login_required
def profile_view(request):
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user.profile)

        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, '✅ Your profile has been updated!')
            return redirect('profile')

    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)

    context = {
        'u_form': u_form,
        'p_form': p_form
    }

    return render(request, 'quizzes/profile.html', context)


# -------------------------------------------------------------------
#  PASSWORD RESET VIEWS & LOGIN
# -------------------------------------------------------------------
class CustomPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    form_class = CustomSetPasswordForm
    template_name = 'quizzes/password_reset_confirm.html'
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        messages.success(self.request, "✅ Password reset successfully! You can now login with your new password.")
        return super().form_valid(form)

class CustomLoginView(auth_views.LoginView):
    template_name = 'quizzes/login.html'
    authentication_form = UserLoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        remember_me = self.request.POST.get('remember_me')
        if remember_me:
            self.request.session.set_expiry(2592000)
        else:
            self.request.session.set_expiry(0)
        return super().form_valid(form)

# 🔒 Secure Class Join
@login_required
def join_class(request, class_id):
    scheduled_class = get_object_or_404(ScheduledClass, id=class_id)
    
    # Check time
    time_diff = scheduled_class.start_time - timezone.now()
    
    # Allow joining if within 15 minutes (900 seconds) or already started
    if time_diff.total_seconds() > 900: 
        return render(request, 'quizzes/class_locked.html', {'class': scheduled_class})
    
    if not scheduled_class.meeting_link:
         messages.error(request, "The meeting link has not been added yet.")
         return redirect('home')
        
    return redirect(scheduled_class.meeting_link)
