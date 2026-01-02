from django.contrib import admin
from .models import Profile, ClassPackage, ScheduledClass, UserSubscription, PaymentHistory

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'gender')

@admin.register(ClassPackage)
class ClassPackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'duration_months', 'max_classes', 'is_active')
    list_filter = ('is_active',)

@admin.register(ScheduledClass)
class ScheduledClassAdmin(admin.ModelAdmin):
    list_display = ('title', 'start_time', 'instructor', 'is_upcoming', 'get_packages')
    list_filter = ('start_time', 'instructor', 'packages')
    ordering = ('start_time',)
    filter_horizontal = ('packages',)

    def get_packages(self, obj):
        return ", ".join([p.name for p in obj.packages.all()])
    get_packages.short_description = 'Packages'

@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'package', 'end_date', 'is_active')
    list_filter = ('is_active', 'package')

@admin.register(PaymentHistory)
class PaymentHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'status', 'payment_date', 'transaction_id')
    list_filter = ('status', 'payment_date')
    readonly_fields = ('payment_date',)

# -------------------------------------------------------------------
#  👤 User Admin Extension (To show Phone Number)
# -------------------------------------------------------------------
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

# Unregister default User admin
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile Info (Phone, Gender, etc)'

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    inlines = (ProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_phone_number', 'is_staff')
    
    def get_phone_number(self, obj):
        return obj.profile.phone_number if hasattr(obj, 'profile') else '-'
    get_phone_number.short_description = 'Phone Number'  # Column header name
