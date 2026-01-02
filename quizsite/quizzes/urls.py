from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    # 🏠 Home & Auth
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    path('activate/<uidb64>/<token>/', views.activate, name='activate'),
    path('profile/', views.profile_view, name='profile'),
    
    # 📅 Singing Classes Layout
    path('schedule/', views.schedule_view, name='schedule'),
    path('category/<slug:slug>/', views.category_detail, name='category_detail'),
    path('class/join/<int:class_id>/', views.join_class, name='join_class'),
    path('packages/', views.packages_view, name='packages'),
    path('payment/initiate/<int:package_id>/', views.payment_initiate, name='payment_initiate'),
    path('payment/verify/', views.payment_verify, name='payment_verify'),
    path('payment/history/', views.payment_history, name='payment_history'),

    # 🔐 Password Reset
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='quizzes/password_reset.html',
        email_template_name='quizzes/password_reset_email.html',
        form_class=views.EmailValidationPasswordResetForm
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='quizzes/password_reset_done.html'
    ), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', views.CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    
    path('password-change/', auth_views.PasswordChangeView.as_view(template_name='quizzes/password_change.html'), name='password_change'),
    path('password-change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='quizzes/password_change_done.html'), name='password_change_done'),
]
