from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import datetime

# -------------------------------------------------------------------
#  👤 Profile Model (Kept for User Extension)
# -------------------------------------------------------------------
class Profile(models.Model):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    profile_pic = models.ImageField(upload_to='profiles/', blank=True, null=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.profile.save()
    except Exception:
        Profile.objects.create(user=instance)


# -------------------------------------------------------------------
#  📦 Class Packages (e.g., Bronze, Silver, Gold)
# -------------------------------------------------------------------
class ClassPackage(models.Model):
    name = models.CharField(max_length=100)  # e.g. "Monthly Beginner", "Pro Vocalist"
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_months = models.PositiveIntegerField(default=1, help_text="Duration of package in months")
    max_classes = models.PositiveIntegerField(default=8, help_text="Number of classes included")
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} - ${self.price}"


# -------------------------------------------------------------------
#  📅 Scheduled Classes
# -------------------------------------------------------------------
class ScheduledClass(models.Model):
    title = models.CharField(max_length=200)  # e.g. "Vocal Warmups 101"
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    instructor = models.CharField(max_length=100, default="Head Coach")
    
    # Link Class to Specific Packages (Empty = Available to All/Universal)
    packages = models.ManyToManyField(ClassPackage, blank=True, related_name="classes")
    
    meeting_link = models.URLField(blank=True, null=True, help_text="Zoom/Meet link for the class")
    description = models.TextField(blank=True)
    
    class Meta:
        ordering = ['start_time']
        verbose_name_plural = "Scheduled Classes"

    def __str__(self):
        return f"{self.title} ({self.start_time.strftime('%b %d, %H:%M')})"
    
    @property
    def is_upcoming(self):
        return self.start_time > timezone.now()


# -------------------------------------------------------------------
#  💳 User Subscription & Payments
# -------------------------------------------------------------------
class UserSubscription(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')
    package = models.ForeignKey(ClassPackage, on_delete=models.SET_NULL, null=True, blank=True)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.user.username} - {self.package.name if self.package else 'No Package'}"
    
    @property
    def is_expired(self):
        return timezone.now() > self.end_date

class PaymentHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    package = models.ForeignKey(ClassPackage, on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_id = models.CharField(max_length=100, unique=True)
    payment_date = models.DateTimeField(auto_now_add=True)
    status_choices = [
        ('SUCCESS', 'Success'),
        ('PENDING', 'Pending'),
        ('FAILED', 'Failed'),
    ]
    status = models.CharField(max_length=10, choices=status_choices, default='PENDING')

    class Meta:
        ordering = ['-payment_date']
        verbose_name_plural = "Payment History"

    def __str__(self):
        return f"{self.user.username} - {self.amount} ({self.status})"
