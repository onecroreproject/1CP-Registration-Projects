from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from apps.admin_module.forms import AdminSignupForm, LoginForm, DomainForm
from django.contrib.auth.models import User
import re
from django.db.models import Q
from django.utils.timezone import now , timedelta
from datetime import datetime
from django.db.models import Q, Sum
from django.utils.timezone import localtime
from apps.project.models import ProjectRegistration,ProjectPayment, ProjectStudentDetail
from django.db.models import Prefetch
from django.core.paginator import Paginator
from django import forms
from django.db import models

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
import json
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
import razorpay
from apps.project.views import generate_team_id 
from apps.project.views import send_payment_email_django,send_failure_email_django
from decimal import Decimal, InvalidOperation

from .models import Domain, Profile
from django.db.models import Sum, Count, Q, Prefetch
from django.urls import reverse
from django.http import HttpResponseRedirect



def create_sales(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if password1 != password2:
            messages.error(request, "Passwords do not match.")
            return redirect('admin_project:create_sales')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect('admin_project:create_sales')

        user = User.objects.create_user(username=username, email=email, password=password1)
        profile = Profile.objects.get(user=user)
        profile.role = 'sales'
        profile.save()

        messages.success(request, "Sales account created successfully.")
        return redirect('admin_project:main_dashboard')
    return render(request, 'admin/project/create_sales.html', {'title': 'Sales Signup'})


def create_developer(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if password1 != password2:
            messages.error(request, "Passwords do not match.")
            return redirect('admin_project:main_dashboard')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect('admin_project:create_developer')

        user = User.objects.create_user(username=username, email=email, password=password1)
        profile = Profile.objects.get(user=user)
        profile.role = 'developer'
        profile.save()

        messages.success(request, "Developer account created successfully.")
        return redirect('admin_project:main_dashboard') 
    return render(request, 'admin/project/create_developer.html', {'title': 'Developer Signup'})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('admin_project:main_dashboard')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)
                profile, _ = Profile.objects.get_or_create(user=user)
                role = profile.role

                messages.success(request, f'Welcome {username}!')

                if role == 'main_admin' or user.is_superuser:
                    return redirect('admin_project:main_dashboard')
                elif role == 'sales':
                    return redirect('admin_project:sales_dashboard')
                elif role == 'developer':
                    return redirect('admin_project:developer_dashboard')
                else:
                    messages.error(request, f'Invalid role: {role}. Please contact admin.')
                    logout(request)
                    return redirect('admin_project:login')
            else:
                messages.error(request, 'Invalid username or password')
                return redirect('admin_project:login')
    else:
        form = LoginForm()

    return render(request, 'admin/project/login.html', {'form': form, 'title': 'Login'})


def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('admin_project:login')


@login_required
def main_dashboard(request):
    # Allow access if user is main_admin or superuser
    if getattr(request.user.profile, 'role', None) != 'main_admin' and not request.user.is_superuser:
        return redirect('admin_project:login')
    
    return render(request, 'admin/project/index.html')



@login_required
def project(request):
    today = now().date()
    yesterday = today - timedelta(days=1)

    total_ids = ProjectRegistration.objects.filter(
        Q(team_id__isnull=False) & ~Q(team_id__exact='')
    ).count()

    daily_ids = ProjectRegistration.objects.filter(
        Q(team_id__isnull=False) & ~Q(team_id__exact=''),
        date__date=today
    ).count()

    total_sales = ProjectRegistration.objects.aggregate(
        total=Sum('paid_amount')
    )['total'] or 0

    daily_sales_today = ProjectRegistration.objects.filter(
        date__date=today,
        paid_amount__isnull=False
    ).aggregate(total=Sum('paid_amount'))['total'] or 0

    daily_sales_yesterday = ProjectRegistration.objects.filter(
        date__date=yesterday,
        paid_amount__isnull=False
    ).aggregate(total=Sum('paid_amount'))['total'] or 0

    percent_change = (
        ((daily_sales_today - daily_sales_yesterday) / daily_sales_yesterday) * 100
        if daily_sales_yesterday > 0 else (100 if daily_sales_today > 0 else 0)
    )

    current_date = localtime(now()).strftime('%B %d, %Y')

    # Prefetch student details
    overview_queryset = ProjectRegistration.objects.prefetch_related(
        Prefetch('students', queryset=ProjectStudentDetail.objects.order_by('id'), to_attr='ordered_students')
    ).order_by('-team_id')

    paginator = Paginator(overview_queryset, 5)
    page_number = request.GET.get('page')
    overviews = paginator.get_page(page_number)

    transactions = (
        ProjectPayment.objects
        .select_related('registration')
        .prefetch_related(
            Prefetch('registration__students', queryset=ProjectStudentDetail.objects.order_by('id'), to_attr='ordered_students')
        )
        .filter(registration__isnull=False)
        .order_by('-registration__team_id')[:10]
    )

    return render(request, 'admin/project/project.html', {
        'total_ids': total_ids,
        'daily_ids': daily_ids,
        'total_sales': total_sales,
        'daily_sales_today': daily_sales_today,
        'percent_change': round(percent_change, 2),
        'current_date': current_date,
        'overviews': overviews,
        'transactions': transactions,
    })


@login_required
def registration(request):
    today = now().date()
    yesterday = today - timedelta(days=1)

    total_ids = ProjectRegistration.objects.filter(
        Q(team_id__isnull=False) & ~Q(team_id__exact='')
    ).count()
    daily_ids = ProjectRegistration.objects.filter(
        Q(team_id__isnull=False) & ~Q(team_id__exact=''),
        date__date=today
    ).count()

    total_sales = ProjectRegistration.objects.aggregate(total=Sum('paid_amount'))['total'] or 0
    daily_sales_today = ProjectRegistration.objects.filter(
        date__date=today, paid_amount__isnull=False
    ).aggregate(total=Sum('paid_amount'))['total'] or 0
    daily_sales_yesterday = ProjectRegistration.objects.filter(
        date__date=yesterday, paid_amount__isnull=False
    ).aggregate(total=Sum('paid_amount'))['total'] or 0

    percent_change = (
        ((daily_sales_today - daily_sales_yesterday) / daily_sales_yesterday) * 100
        if daily_sales_yesterday > 0 else (100 if daily_sales_today > 0 else 0)
    )
    current_date = localtime(now()).strftime('%B %d, %Y')

    total_delivery = ProjectRegistration.objects.filter(delivery_date__isnull=False).count()
    daily_delivery = ProjectRegistration.objects.filter(delivery_date=today).count()

    # Status counts: include nulls and correct spelling
    status_counts = ProjectRegistration.objects.values_list('project_status').annotate(count=Count('id'))
    status_dict = {}
    for (status, count) in status_counts:
        key = (status or 'Not Started').strip()
        status_dict[key] = status_dict.get(key, 0) + count

    status_summary = {
        'not_started': status_dict.get('Not Started', 0),
        'on_going': status_dict.get('On Going', 0),
        'completed': status_dict.get('Completed', 0),
        'delivered': status_dict.get('Delivered', 0),
        'cancelled': status_dict.get('Canceled', 0) or status_dict.get('Cancelled', 0),
    }

    overviews = ProjectRegistration.objects.prefetch_related(
        Prefetch('students', queryset=ProjectStudentDetail.objects.order_by('id'), to_attr='ordered_students'),
        Prefetch('projectpayment_set', queryset=ProjectPayment.objects.order_by('-created_at'), to_attr='related_payments')
    ).order_by('-team_id')

    transactions = ProjectPayment.objects.select_related('registration').prefetch_related(
        Prefetch('registration__students', queryset=ProjectStudentDetail.objects.order_by('id'), to_attr='ordered_students')
    ).filter(registration__isnull=False).order_by('-registration__team_id')[:10]

    domains = Domain.objects.all()

    return render(request, 'admin/project/registration.html', {
        'total_ids': total_ids,
        'daily_ids': daily_ids,
        'total_sales': total_sales,
        'daily_sales_today': daily_sales_today,
        'percent_change': round(percent_change, 2),
        'current_date': current_date,
        'overviews': overviews,
        'transactions': transactions,
        'total_delivery': total_delivery,
        'daily_delivery': daily_delivery,
        'domains': domains,
        'status_summary': status_summary,
    })






@login_required
def payment(request):
    today = now().date()
    yesterday = today - timedelta(days=1)

    # === Total & Daily IDs ===
    total_ids = ProjectRegistration.objects.filter(
        Q(team_id__isnull=False) & ~Q(team_id__exact='')
    ).count()

    daily_ids = ProjectRegistration.objects.filter(
        Q(team_id__isnull=False) & ~Q(team_id__exact=''),
        date__date=today
    ).count()

    # === Sales Totals ===
    total_sales = ProjectRegistration.objects.aggregate(
        total=Sum('paid_amount')
    )['total'] or 0

    daily_sales_today = ProjectRegistration.objects.filter(
        date__date=today,
        paid_amount__isnull=False
    ).aggregate(total=Sum('paid_amount'))['total'] or 0

    daily_sales_yesterday = ProjectRegistration.objects.filter(
        date__date=yesterday,
        paid_amount__isnull=False
    ).aggregate(total=Sum('paid_amount'))['total'] or 0

    # === % Change ===
    percent_change = (
        ((daily_sales_today - daily_sales_yesterday) / daily_sales_yesterday) * 100
        if daily_sales_yesterday > 0 else (100 if daily_sales_today > 0 else 0)
    )

    current_date = localtime(now()).strftime('%B %d, %Y')

    # === Prefetch Payments ===
    payment_qs = ProjectPayment.objects.select_related('registration')
    payment_map = {
        p.registration_id: p for p in payment_qs if p.registration_id is not None
    }

    # === Project Registrations Overview with students ===
    overviews = ProjectRegistration.objects.prefetch_related(
        Prefetch('students', queryset=ProjectStudentDetail.objects.order_by('id'), to_attr='ordered_students'),
        Prefetch('projectpayment_set', queryset=ProjectPayment.objects.order_by('-created_at'), to_attr='related_payments')  # add this line
    ).order_by('-team_id')

    # === Recent Transactions ===
    transactions = (
        ProjectPayment.objects
        .select_related('registration')
        .prefetch_related(
            Prefetch(
                'registration__students',
                queryset=ProjectStudentDetail.objects.order_by('id'),
                to_attr='ordered_students'
            )
        )
        .filter(registration__isnull=False)
        .order_by('-registration__team_id')[:10]
    )

    return render(request, 'admin/project/payment.html', {
        'total_ids': total_ids,
        'daily_ids': daily_ids,
        'total_sales': total_sales,
        'daily_sales_today': daily_sales_today,
        'percent_change': round(percent_change, 2),
        'current_date': current_date,
        'overviews': overviews,
        'transactions': transactions,
        'payment_map': payment_map,
    })

@login_required
def payment_history_view(request):
    profile = getattr(request.user, "profile", None)

    if not profile:
        return redirect('admin_project:login')

    # Common transaction query
    transactions = (
        ProjectPayment.objects
        .select_related('registration')
        .prefetch_related(
            Prefetch(
                'registration__students',
                queryset=ProjectStudentDetail.objects.order_by('id'),
                to_attr='ordered_students'
            )
        )
        .filter(registration__isnull=False)
        .order_by('-created_at')
    )

    # Only superuser can access main payment history
    if request.user.is_superuser:
        return render(request, 'admin/project/payment_history.html', {
            'transactions': transactions,
        })
    elif profile.role == 'sales':
        return render(request, 'admin/project/sales_payment_history.html', {
            'transactions': transactions,
        })
    else:
        return redirect('admin_project:login')



@login_required
def sales_dashboard(request):
    if request.user.profile.role != 'sales':
        return redirect('admin_project:login')
    return render(request, 'admin/project/sales_index.html')


@login_required
def sales_project(request):
    # Ensure only sales users access this view
    profile = getattr(request.user, "profile", None)
    if not profile or profile.role != 'sales':
        return redirect('admin_project:login')

    today = now().date()
    yesterday = today - timedelta(days=1)

    total_ids = ProjectRegistration.objects.filter(
        Q(team_id__isnull=False) & ~Q(team_id__exact='')
    ).count()

    daily_ids = ProjectRegistration.objects.filter(
        Q(team_id__isnull=False) & ~Q(team_id__exact=''),
        date__date=today
    ).count()

    total_sales = ProjectRegistration.objects.aggregate(
        total=Sum('paid_amount')
    )['total'] or 0

    daily_sales_today = ProjectRegistration.objects.filter(
        date__date=today,
        paid_amount__isnull=False
    ).aggregate(total=Sum('paid_amount'))['total'] or 0

    daily_sales_yesterday = ProjectRegistration.objects.filter(
        date__date=yesterday,
        paid_amount__isnull=False
    ).aggregate(total=Sum('paid_amount'))['total'] or 0

    percent_change = (
        ((daily_sales_today - daily_sales_yesterday) / daily_sales_yesterday) * 100
        if daily_sales_yesterday > 0 else (100 if daily_sales_today > 0 else 0)
    )

    current_date = localtime(now()).strftime('%B %d, %Y')

    overviews = ProjectRegistration.objects.all().order_by('-team_id')[:10]

    transactions = (
        ProjectPayment.objects
        .select_related('registration')
        .prefetch_related(
            Prefetch(
                'registration__students',
                queryset=ProjectStudentDetail.objects.order_by('id'),
                to_attr='ordered_students'
            )
        )
        .filter(registration__isnull=False)
        .order_by('-registration__team_id')[:10]
    )

    pending_payments = ProjectPayment.objects.filter(
        selected_payment_method='cash',
        payment_status__isnull=True
    ).order_by('-created_at')

    return render(request, 'admin/project/sales_project.html', {
        'total_ids': total_ids,
        'daily_ids': daily_ids,
        'total_sales': total_sales,
        'daily_sales_today': daily_sales_today,
        'percent_change': round(percent_change, 2),
        'current_date': current_date,
        'overviews': overviews,
        'transactions': transactions,
        'payments': pending_payments,
    })




@login_required
def sales_registration(request):
    if request.user.profile.role != 'sales':
        return redirect('admin_project:login')

    today = now().date()
    yesterday = today - timedelta(days=1)

    total_ids = ProjectRegistration.objects.filter(
        Q(team_id__isnull=False) & ~Q(team_id__exact='')
    ).count()

    daily_ids = ProjectRegistration.objects.filter(
        Q(team_id__isnull=False) & ~Q(team_id__exact=''),
        date__date=today
    ).count()

    total_sales = ProjectRegistration.objects.aggregate(
        total=Sum('paid_amount')
    )['total'] or 0

    daily_sales_today = ProjectRegistration.objects.filter(
        date__date=today,
        paid_amount__isnull=False
    ).aggregate(total=Sum('paid_amount'))['total'] or 0

    daily_sales_yesterday = ProjectRegistration.objects.filter(
        date__date=yesterday,
        paid_amount__isnull=False
    ).aggregate(total=Sum('paid_amount'))['total'] or 0

    percent_change = (
        ((daily_sales_today - daily_sales_yesterday) / daily_sales_yesterday) * 100
        if daily_sales_yesterday > 0 else (100 if daily_sales_today > 0 else 0)
    )

    current_date = localtime(now()).strftime('%B %d, %Y')
    total_delivery = ProjectRegistration.objects.filter(delivery_date__isnull=False).count()
    daily_delivery = ProjectRegistration.objects.filter(delivery_date=today).count()

    # --- Domain Summary ---
    domains = Domain.objects.all()

    # --- Status Summary ---
    status_counts = ProjectRegistration.objects.values_list('project_status').annotate(count=Count('id'))
    status_dict = {}
    for (status, count) in status_counts:
        key = (status or 'Not Started').strip()
        status_dict[key] = status_dict.get(key, 0) + count

    status_summary = {
        'not_started': status_dict.get('Not Started', 0),
        'on_going': status_dict.get('On Going', 0),
        'completed': status_dict.get('Completed', 0),
        'delivered': status_dict.get('Delivered', 0),
        'cancelled': status_dict.get('Canceled', 0) or status_dict.get('Cancelled', 0),
    }

    overviews = ProjectRegistration.objects.prefetch_related(
        Prefetch('students', queryset=ProjectStudentDetail.objects.order_by('id'), to_attr='ordered_students'),
        Prefetch('projectpayment_set', queryset=ProjectPayment.objects.order_by('-created_at'), to_attr='related_payments')
    ).order_by('-team_id')

    transactions = ProjectPayment.objects.select_related('registration').prefetch_related(
        Prefetch('registration__students', queryset=ProjectStudentDetail.objects.order_by('id'), to_attr='ordered_students')
    ).filter(registration__isnull=False).order_by('-registration__team_id')[:10]

    return render(request, 'admin/project/sales_registration.html', {
        'total_ids': total_ids,
        'daily_ids': daily_ids,
        'total_sales': total_sales,
        'daily_sales_today': daily_sales_today,
        'percent_change': round(percent_change, 2),
        'current_date': current_date,
        'overviews': overviews,
        'transactions': transactions,
        'total_delivery': total_delivery,
        'daily_delivery': daily_delivery,
        'domains': domains,
        'status_summary': status_summary,
    })



@login_required
def sales_payment(request):
    if request.user.profile.role != 'sales':
        return redirect('admin_project:login')

    today = now().date()
    yesterday = today - timedelta(days=1)

    total_ids = ProjectRegistration.objects.filter(
        Q(team_id__isnull=False) & ~Q(team_id__exact='')
    ).count()

    daily_ids = ProjectRegistration.objects.filter(
        Q(team_id__isnull=False) & ~Q(team_id__exact=''),
        date__date=today
    ).count()

    total_sales = ProjectRegistration.objects.aggregate(
        total=Sum('paid_amount')
    )['total'] or 0

    daily_sales_today = ProjectRegistration.objects.filter(
        date__date=today,
        paid_amount__isnull=False
    ).aggregate(total=Sum('paid_amount'))['total'] or 0

    daily_sales_yesterday = ProjectRegistration.objects.filter(
        date__date=yesterday,
        paid_amount__isnull=False
    ).aggregate(total=Sum('paid_amount'))['total'] or 0

    percent_change = ((daily_sales_today - daily_sales_yesterday) / daily_sales_yesterday * 100
                      if daily_sales_yesterday > 0 else (100 if daily_sales_today > 0 else 0))

    current_date = localtime(now()).strftime('%B %d, %Y')

    payment_qs = ProjectPayment.objects.select_related('registration')
    payment_map = {p.registration_id: p for p in payment_qs if p.registration_id is not None}

    overviews = ProjectRegistration.objects.prefetch_related(
        Prefetch(
            'students',
            queryset=ProjectStudentDetail.objects.order_by('id'),
            to_attr='ordered_students'
        )
    ).order_by('-team_id')

    transactions = (
        ProjectPayment.objects
        .select_related('registration')
        .prefetch_related(
            Prefetch(
                'registration__students',
                queryset=ProjectStudentDetail.objects.order_by('id'),
                to_attr='ordered_students'
            )
        )
        .filter(registration__isnull=False)
        .order_by('-registration__team_id')[:10]
    )

    return render(request, 'admin/project/sales_payment.html', {
        'total_ids': total_ids,
        'daily_ids': daily_ids,
        'total_sales': total_sales,
        'daily_sales_today': daily_sales_today,
        'percent_change': round(percent_change, 2),
        'current_date': current_date,
        'overviews': overviews,
        'transactions': transactions,
        'payment_map': payment_map,
    })


@login_required
def developer_dashboard(request):
    # Role-based access control
    if not hasattr(request.user, 'profile') or request.user.profile.role != 'developer':
        return redirect('admin_project:login')

    today = now().date()
    yesterday = today - timedelta(days=1)

    total_ids = ProjectRegistration.objects.filter(
        Q(team_id__isnull=False) & ~Q(team_id__exact='')
    ).count()

    daily_ids = ProjectRegistration.objects.filter(
        Q(team_id__isnull=False) & ~Q(team_id__exact=''),
        date__date=today
    ).count()

    total_sales = ProjectRegistration.objects.aggregate(
        total=Sum('paid_amount')
    )['total'] or 0

    daily_sales_today = ProjectRegistration.objects.filter(
        date__date=today,
        paid_amount__isnull=False
    ).aggregate(total=Sum('paid_amount'))['total'] or 0

    daily_sales_yesterday = ProjectRegistration.objects.filter(
        date__date=yesterday,
        paid_amount__isnull=False
    ).aggregate(total=Sum('paid_amount'))['total'] or 0

    percent_change = (
        ((daily_sales_today - daily_sales_yesterday) / daily_sales_yesterday) * 100
        if daily_sales_yesterday > 0
        else 100 if daily_sales_today > 0 else 0
    )

    current_date = localtime(now()).strftime('%B %d, %Y')

    total_delivery = ProjectRegistration.objects.filter(delivery_date__isnull=False).count()
    daily_delivery = ProjectRegistration.objects.filter(delivery_date=today).count()

    # Domain summary (count per domain name)
    domains = Domain.objects.all()

    # Project Status Summary
    status_counts = ProjectRegistration.objects.values_list('project_status').annotate(count=Count('id'))
    status_dict = {}
    for (status, count) in status_counts:
        key = (status or 'Not Started').strip()
        status_dict[key] = status_dict.get(key, 0) + count

    status_summary = {
        'not_started': status_dict.get('Not Started', 0),
        'on_going': status_dict.get('On Going', 0),
        'completed': status_dict.get('Completed', 0),
        'delivered': status_dict.get('Delivered', 0),
        'cancelled': status_dict.get('Canceled', 0) or status_dict.get('Cancelled', 0),
    }

    # Main data
    overviews = ProjectRegistration.objects.prefetch_related(
        Prefetch('students', queryset=ProjectStudentDetail.objects.order_by('id'), to_attr='ordered_students'),
        Prefetch('projectpayment_set', queryset=ProjectPayment.objects.order_by('-created_at'), to_attr='related_payments')
    ).order_by('-team_id')

    transactions = ProjectPayment.objects.select_related('registration').prefetch_related(
        Prefetch('registration__students', queryset=ProjectStudentDetail.objects.order_by('id'), to_attr='ordered_students')
    ).filter(registration__isnull=False).order_by('-registration__team_id')[:10]

    return render(request, 'admin/project/developer_dashboard.html', {
        'total_ids': total_ids,
        'daily_ids': daily_ids,
        'total_sales': total_sales,
        'daily_sales_today': daily_sales_today,
        'percent_change': round(percent_change, 2),
        'current_date': current_date,
        'overviews': overviews,
        'transactions': transactions,
        'total_delivery': total_delivery,
        'daily_delivery': daily_delivery,
        'domains': domains,
        'status_summary': status_summary,
    })


@login_required
def update_project(request):
    if request.method == "POST":
        profile = getattr(request.user, "profile", None)
        if not request.user.is_superuser and (not profile or profile.role not in ['main_admin', 'developer', 'sales']):
            messages.error(request, "You do not have permission to update this project.")
            return redirect('login')

        project_id = request.POST.get("project_id")
        project = get_object_or_404(ProjectRegistration, id=project_id)

        # Update logic
        project.team_id = request.POST.get("team_id")
        project.delivery_date = request.POST.get("delivery_date") or None
        # project.delivery_status = request.POST.get("delivery_status")
        project.name = request.POST.get("name")
        project.contact = request.POST.get("contact")
        project.whatsapp_no = request.POST.get("whatsapp_no")
        project.email = request.POST.get("email")
        project.college_name = request.POST.get("college") or project.college_name
        project.degree = request.POST.get("degree") or project.degree
        project.department = request.POST.get("department")
        project.domain = request.POST.get("domain")
        project.topic = request.POST.get("topic")
        project.workflow_abstract = request.POST.get("workflow_abstract")
        project.ppt_file = request.POST.get("ppt_file")
        project.output_video = request.POST.get("output_video")
        project.source_code = request.POST.get("source_code")
        project.complete_document = request.POST.get("complete_document")
        project.explanation_file = request.POST.get("explanation_file")
        project.project_status = request.POST.get("project_status")
        project.developer_name = request.POST.get("developer_name")
        project.delivery_person_name = request.POST.get("delivery_person_name")
        project.reason = request.POST.get("reason")

        project.save()
        messages.success(request, "Project updated successfully.")

        # Role-based redirection
        if request.user.is_superuser or profile.role == 'main_admin':
            return redirect('admin_project:registration')
        elif profile.role == 'developer':
            return redirect('admin_project:developer_dashboard')
        elif profile.role == 'sales':
            return redirect('admin_project:sales_registration')
        else:
            return redirect('login')

@login_required
def delete_project(request):
    if request.method == "POST":
        profile = getattr(request.user, "profile", None)
        if not request.user.is_superuser and (not profile or profile.role != 'main_admin'):
            messages.error(request, "Only the Main Admin can delete projects.")
            return redirect('admin_project:registration')

        project = get_object_or_404(ProjectRegistration, id=request.POST.get('project_id'))
        project.delete()
        messages.success(request, "Project deleted successfully.")
        return redirect('admin_project:registration')



@login_required
def update_payment(request):
    if request.method == "POST":
        profile = getattr(request.user, "profile", None)
        if not request.user.is_superuser and (not profile or profile.role not in ['main_admin', 'developer', 'sales']):
            messages.error(request, "You do not have permission to update this project.")
            return redirect('login')

        project_id = request.POST.get("project_id")
        project = get_object_or_404(ProjectRegistration, id=project_id)

        #  Directly update only the required 5 fields
        project.domain = request.POST.get("domain")
        project.topic = request.POST.get("topic")

        try:
            total_amount = float(request.POST.get("total_amount") or 0)
            paid_amount = float(request.POST.get("paid_amount") or 0)
        except ValueError:
            messages.error(request, "Invalid amount entered.")
            return redirect('admin_project:payment')

        balance_amount = max(0, total_amount - paid_amount)

        project.total_amount = total_amount
        project.paid_amount = paid_amount
        project.balance_amount = balance_amount

        project.save()
        messages.success(request, "Payment details updated successfully.")

        # Role-based redirection
        if request.user.is_superuser or profile.role == 'main_admin':
            return redirect('admin_project:payment')
        elif profile.role == 'developer':
            return redirect('admin_project:developer_dashboard')
        elif profile.role == 'sales':
            return redirect('admin_project:sales_payment')
        else:
            return redirect('login')

    messages.error(request, "Invalid request method.")
    return redirect('admin_project:payment')


@login_required
def delete_payment(request):
    if request.method == "POST":
        profile = getattr(request.user, "profile", None)
        if not request.user.is_superuser and (not profile or profile.role != 'main_admin'):
            messages.error(request, "Only the Main Admin can delete projects.")
            return redirect('admin_project:registration')

        project = get_object_or_404(ProjectRegistration, id=request.POST.get('project_id'))
        project.delete()
        messages.success(request, "Project deleted successfully.")
        return redirect('admin_project:payment')
    

client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    



@login_required
def sales_accept_payment(request):
    if request.method != 'POST':
        messages.error(request, "Invalid request method.")
        return redirect('admin_project:sales_dashboard')

    payment_id = request.POST.get('payment_id')
    amount = request.POST.get('amount')

    if not payment_id or not amount:
        messages.error(request, "Missing payment details.")
        return redirect('admin_project:sales_dashboard')

    try:
        amount = Decimal(amount)
    except (InvalidOperation, TypeError):
        messages.error(request, "Invalid amount entered.")
        return redirect('admin_project:sales_dashboard')
    
    if amount <= 0:
        messages.error(request, "Payment amount must be greater than zero.")
        return redirect('admin_project:sales_dashboard')

    payment = get_object_or_404(ProjectPayment, id=payment_id)
    registration = payment.registration


    cashpay_id = generate_cashpay_id(payment.bill_no)
    if not cashpay_id:
        messages.error(request, "Invalid bill number. Could not generate cash payment ID.")
        return redirect('admin_project:sales_dashboard')

    # Update Payment details
    payment.razorpay_payment_id = cashpay_id
    payment.payment_status = 'success'
    payment.paid = True
    payment.razorpay_status = 'captured'
    payment.razorpay_method = 'cash'
    payment.razorpay_contact = payment.phone
    payment.razorpay_description = 'Cash Payment Confirmed'
    payment.bank = 'N/A'
    payment.selected_payment_method = 'cash'
    payment.save()

    if registration:
        # Generate team_id if not exists
        if not registration.team_id:
            registration.team_id = generate_team_id()
            registration.save()

            # Send confirmation email
            send_payment_email_django(payment, registration)
            return redirect('project:success', payment_id=cashpay_id)

        # Update paid and balance amounts
        registration.paid_amount = (registration.paid_amount or Decimal('0.00')) + amount

        if registration.total_amount:
            registration.balance_amount = registration.total_amount - registration.paid_amount
        else:
            registration.balance_amount = 0

        registration.save()

        send_payment_email_django(payment, registration)
        

    messages.success(request, "Payment processed and email sent successfully.")
    return redirect('admin_project:sales_dashboard')


@login_required
def sales_decline_payment(request):
    if request.method == 'POST':
        payment_id = request.POST.get('payment_id')
        decline_reason = request.POST.get('decline_reason')
        payment = get_object_or_404(ProjectPayment, id=payment_id)

        payment.payment_status = 'failed'
        payment.decline_reason = decline_reason
        payment.save()

        registration = payment.registration
        # Send failure email for cash declines
        if registration:
            send_failure_email_django(payment, registration)

        messages.info(request, f"Payment from {payment.name} has been declined and email sent.")
    else:
        messages.error(request, "Invalid request.")
    return redirect('admin_project:sales_dashboard')




def generate_cashpay_id(bill_no):
    now = timezone.now()
    prefix = f"CASH\\{now.year}\\{now.month:02d}" 

    try:
        bill_no_number = int(str(bill_no).lstrip('B'))
        if bill_no_number <= 0:
            raise ValueError("Bill number cannot be zero or negative.")
    except (ValueError, TypeError, AttributeError):
        return None  

    id_number = f"{bill_no_number:05d}"
    return f"{prefix}\\{id_number}"



@login_required
def sales_edit_payment(request):
    if request.method == 'POST':
        payment_id = request.POST.get('payment_id')
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        amount = request.POST.get('amount')

        # Convert amount to Decimal safely
        try:
            amount_decimal = Decimal(amount)
        except:
            messages.error(request, "Invalid amount entered.")
            return redirect('admin_project:sales_dashboard')

        # Update Payment Table
        payment = get_object_or_404(ProjectPayment, id=payment_id)
        payment.name = name
        payment.email = email
        payment.phone = phone
        payment.amount = amount_decimal
        payment.save()

        registration = payment.registration

        if registration:
            # Update ProjectRegistration table
            registration.paid_amount = amount_decimal
            registration.name = name
            registration.contact = phone
            registration.email = email

            # Ensure total_amount is not None
            total = registration.total_amount or Decimal('0.00')
            registration.balance_amount = total - amount_decimal

            registration.save()

            # Update StudentDetail table (first student)
            first_student = ProjectStudentDetail.objects.filter(registration=registration).first()
            if first_student:
                first_student.student_name = name.split()[0]  # Just first name
                first_student.email_id = email
                first_student.contact_no = phone
                first_student.save()

        messages.success(request, f"Payment and related records updated successfully for {name}.")
    else:
        messages.error(request, "Invalid request.")

    return redirect('admin_project:sales_dashboard')

@login_required
def create_domain(request):
    form = DomainForm()
    selected_domain = None

    if request.method == 'POST':
        if 'add_domain' in request.POST:
            form = DomainForm(request.POST)
            if form.is_valid():
                form.save()
                return redirect('admin_project:create_domain')
            else:
                print("Form errors:", form.errors)
        elif 'select_domain' in request.POST:
            selected_domain = request.POST.get('selected_domain')

    domains = Domain.objects.all()
    return render(request, 'admin/project/create_domain.html', {
        'form': form,
        'domains': domains,
        'selected_domain': selected_domain,
    })




