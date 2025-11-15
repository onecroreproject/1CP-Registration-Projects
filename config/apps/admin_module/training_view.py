from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required


from django.db.models import Q
from django.utils.timezone import now , timedelta

from django.db.models import Q, Sum
from django.utils.timezone import localtime
from apps.training.models import TrainingRegistration, TrainingPayment, TrainingStudentDetail
from django.db.models import Prefetch
from django.core.paginator import Paginator


from django.shortcuts import get_object_or_404

from django.contrib import messages
from django.utils import timezone
from apps.training.views import generate_team_id 
from apps.training.views import send_payment_email_training ,send_failure_email_training
from decimal import Decimal, InvalidOperation

from apps.admin_module.models import Domain
from django.db.models import Sum, Count, Q, Prefetch



@login_required
def project(request):
    today = now().date()
    yesterday = today - timedelta(days=1)

    total_ids = TrainingRegistration.objects.filter(
        Q(team_id__isnull=False) & ~Q(team_id__exact='')
    ).count()

    daily_ids = TrainingRegistration.objects.filter(
        Q(team_id__isnull=False) & ~Q(team_id__exact=''),
        date__date=today
    ).count()

    total_sales = TrainingRegistration.objects.aggregate(
        total=Sum('paid_amount')
    )['total'] or 0

    daily_sales_today = TrainingRegistration.objects.filter(
        date__date=today,
        paid_amount__isnull=False
    ).aggregate(total=Sum('paid_amount'))['total'] or 0

    daily_sales_yesterday = TrainingRegistration.objects.filter(
        date__date=yesterday,
        paid_amount__isnull=False
    ).aggregate(total=Sum('paid_amount'))['total'] or 0

    percent_change = (
        ((daily_sales_today - daily_sales_yesterday) / daily_sales_yesterday) * 100
        if daily_sales_yesterday > 0 else (100 if daily_sales_today > 0 else 0)
    )

    current_date = localtime(now()).strftime('%B %d, %Y')

    # Prefetch student details
    overview_queryset = TrainingRegistration.objects.prefetch_related(
        Prefetch('students', queryset=TrainingStudentDetail.objects.order_by('id'), to_attr='ordered_students')
    ).order_by('-team_id')

    paginator = Paginator(overview_queryset, 5)
    page_number = request.GET.get('page')
    overviews = paginator.get_page(page_number)

    transactions = (
        TrainingPayment.objects
        .select_related('registration')
        .prefetch_related(
            Prefetch('registration__students', queryset=TrainingStudentDetail.objects.order_by('id'), to_attr='ordered_students')
        )
        .filter(registration__isnull=False)
        .order_by('-registration__team_id')[:10]
    )

    return render(request, 'admin/training/project.html', {
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

    total_ids = TrainingRegistration.objects.filter(
        Q(team_id__isnull=False) & ~Q(team_id__exact='')
    ).count()
    daily_ids = TrainingRegistration.objects.filter(
        Q(team_id__isnull=False) & ~Q(team_id__exact=''),
        date__date=today
    ).count()

    total_sales = TrainingRegistration.objects.aggregate(total=Sum('paid_amount'))['total'] or 0
    daily_sales_today = TrainingRegistration.objects.filter(
        date__date=today, paid_amount__isnull=False
    ).aggregate(total=Sum('paid_amount'))['total'] or 0
    daily_sales_yesterday = TrainingRegistration.objects.filter(
        date__date=yesterday, paid_amount__isnull=False
    ).aggregate(total=Sum('paid_amount'))['total'] or 0

    percent_change = (
        ((daily_sales_today - daily_sales_yesterday) / daily_sales_yesterday) * 100
        if daily_sales_yesterday > 0 else (100 if daily_sales_today > 0 else 0)
    )
    current_date = localtime(now()).strftime('%B %d, %Y')

    overviews = TrainingRegistration.objects.prefetch_related(
        Prefetch('students', queryset=TrainingStudentDetail.objects.order_by('id'), to_attr='ordered_students'),
        Prefetch('trainingpayment_set', queryset=TrainingPayment.objects.order_by('-created_at'), to_attr='related_payments')
    ).order_by('-team_id')

    transactions = TrainingPayment.objects.select_related('registration').prefetch_related(
        Prefetch('registration__students', queryset=TrainingStudentDetail.objects.order_by('id'), to_attr='ordered_students')
    ).filter(registration__isnull=False).order_by('-registration__team_id')[:10]

    domains = Domain.objects.all()

    return render(request, 'admin/training/registration.html', {
        'total_ids': total_ids,
        'daily_ids': daily_ids,
        'total_sales': total_sales,
        'daily_sales_today': daily_sales_today,
        'percent_change': round(percent_change, 2),
        'current_date': current_date,
        'overviews': overviews,
        'transactions': transactions,
        'domains': domains,

    })


@login_required
def payment(request):
    today = now().date()
    yesterday = today - timedelta(days=1)

    # === Total & Daily IDs ===
    total_ids = TrainingRegistration.objects.filter(
        Q(team_id__isnull=False) & ~Q(team_id__exact='')
    ).count()

    daily_ids = TrainingRegistration.objects.filter(
        Q(team_id__isnull=False) & ~Q(team_id__exact=''),
        date__date=today
    ).count()

    # === Sales Totals ===
    total_sales = TrainingRegistration.objects.aggregate(
        total=Sum('paid_amount')
    )['total'] or 0

    daily_sales_today = TrainingRegistration.objects.filter(
        date__date=today,
        paid_amount__isnull=False
    ).aggregate(total=Sum('paid_amount'))['total'] or 0

    daily_sales_yesterday = TrainingRegistration.objects.filter(
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
    payment_qs = TrainingPayment.objects.select_related('registration')
    payment_map = {
        p.registration_id: p for p in payment_qs if p.registration_id is not None
    }

    # === Project Registrations Overview with students ===
    overviews = TrainingRegistration.objects.prefetch_related(
        Prefetch('students', queryset=TrainingStudentDetail.objects.order_by('id'), to_attr='ordered_students'),
        Prefetch('trainingpayment_set', queryset=TrainingPayment.objects.order_by('-created_at'), to_attr='related_payments')  # add this line
    ).order_by('-team_id')

    # === Recent Transactions ===
    transactions = (
        TrainingPayment.objects
        .select_related('registration')
        .prefetch_related(
            Prefetch(
                'registration__students',
                queryset=TrainingStudentDetail.objects.order_by('id'),
                to_attr='ordered_students'
            )
        )
        .filter(registration__isnull=False)
        .order_by('-registration__team_id')[:10]
    )

    return render(request, 'admin/training/payment.html', {
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
        TrainingPayment.objects
        .select_related('registration')
        .prefetch_related(
            Prefetch(
                'registration__students',
                queryset=TrainingStudentDetail.objects.order_by('id'),
                to_attr='ordered_students'
            )
        )
        .filter(registration__isnull=False)
        .order_by('-created_at')
    )

    # Only superuser can access main payment history
    if request.user.is_superuser:
        return render(request, 'admin/training/payment_history.html', {
            'transactions': transactions,
        })
    elif profile.role == 'sales':
        return render(request, 'admin/training/sales_payment_history.html', {
            'transactions': transactions,
        })
    else:
        return redirect('admin_project:login')


@login_required
def sales_dashboard(request):
    if request.user.profile.role != 'sales':
        return redirect('admin_training:login')
    return render(request, 'admin/training/sales_index.html')


@login_required
def sales_project(request):
    # Ensure only sales users access this view
    profile = getattr(request.user, "profile", None)
    if not profile or profile.role != 'sales':
        return redirect('admin_training:login')

    today = now().date()
    yesterday = today - timedelta(days=1)

    total_ids = TrainingRegistration.objects.filter(
        Q(team_id__isnull=False) & ~Q(team_id__exact='')
    ).count()

    daily_ids = TrainingRegistration.objects.filter(
        Q(team_id__isnull=False) & ~Q(team_id__exact=''),
        date__date=today
    ).count()

    total_sales = TrainingRegistration.objects.aggregate(
        total=Sum('paid_amount')
    )['total'] or 0

    daily_sales_today = TrainingRegistration.objects.filter(
        date__date=today,
        paid_amount__isnull=False
    ).aggregate(total=Sum('paid_amount'))['total'] or 0

    daily_sales_yesterday = TrainingRegistration.objects.filter(
        date__date=yesterday,
        paid_amount__isnull=False
    ).aggregate(total=Sum('paid_amount'))['total'] or 0

    percent_change = (
        ((daily_sales_today - daily_sales_yesterday) / daily_sales_yesterday) * 100
        if daily_sales_yesterday > 0 else (100 if daily_sales_today > 0 else 0)
    )

    current_date = localtime(now()).strftime('%B %d, %Y')

    overviews = TrainingRegistration.objects.all().order_by('-team_id')[:10]

    transactions = (
        TrainingPayment.objects
        .select_related('registration')
        .prefetch_related(
            Prefetch(
                'registration__students',
                queryset=TrainingStudentDetail.objects.order_by('id'),
                to_attr='ordered_students'
            )
        )
        .filter(registration__isnull=False)
        .order_by('-registration__team_id')[:10]
    )

    pending_payments = TrainingPayment.objects.filter(
        selected_payment_method='cash',
        payment_status__isnull=True
    ).order_by('-created_at')

    return render(request, 'admin/training/sales_project.html', {
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
        return redirect('admin_training:login')

    today = now().date()
    yesterday = today - timedelta(days=1)

    total_ids = TrainingRegistration.objects.filter(
        Q(team_id__isnull=False) & ~Q(team_id__exact='')
    ).count()

    daily_ids = TrainingRegistration.objects.filter(
        Q(team_id__isnull=False) & ~Q(team_id__exact=''),
        date__date=today
    ).count()

    total_sales = TrainingRegistration.objects.aggregate(
        total=Sum('paid_amount')
    )['total'] or 0

    daily_sales_today = TrainingRegistration.objects.filter(
        date__date=today,
        paid_amount__isnull=False
    ).aggregate(total=Sum('paid_amount'))['total'] or 0

    daily_sales_yesterday = TrainingRegistration.objects.filter(
        date__date=yesterday,
        paid_amount__isnull=False
    ).aggregate(total=Sum('paid_amount'))['total'] or 0

    percent_change = (
        ((daily_sales_today - daily_sales_yesterday) / daily_sales_yesterday) * 100
        if daily_sales_yesterday > 0 else (100 if daily_sales_today > 0 else 0)
    )

    current_date = localtime(now()).strftime('%B %d, %Y')

    # --- Domain Summary ---
    domains = Domain.objects.all()


    overviews = TrainingRegistration.objects.prefetch_related(
        Prefetch('students', queryset=TrainingStudentDetail.objects.order_by('id'), to_attr='ordered_students'),
        Prefetch('trainingpayment_set', queryset=TrainingPayment.objects.order_by('-created_at'), to_attr='related_payments')
    ).order_by('-team_id')

    transactions = TrainingPayment.objects.select_related('registration').prefetch_related(
        Prefetch('registration__students', queryset=TrainingStudentDetail.objects.order_by('id'), to_attr='ordered_students')
    ).filter(registration__isnull=False).order_by('-registration__team_id')[:10]

    return render(request, 'admin/training/sales_registration.html', {
        'total_ids': total_ids,
        'daily_ids': daily_ids,
        'total_sales': total_sales,
        'daily_sales_today': daily_sales_today,
        'percent_change': round(percent_change, 2),
        'current_date': current_date,
        'overviews': overviews,
        'transactions': transactions,
        'domains': domains,
  
    })



@login_required
def sales_payment(request):
    if request.user.profile.role != 'sales':
        return redirect('admin_training:login')

    today = now().date()
    yesterday = today - timedelta(days=1)

    total_ids = TrainingRegistration.objects.filter(
        Q(team_id__isnull=False) & ~Q(team_id__exact='')
    ).count()

    daily_ids = TrainingRegistration.objects.filter(
        Q(team_id__isnull=False) & ~Q(team_id__exact=''),
        date__date=today
    ).count()

    total_sales = TrainingRegistration.objects.aggregate(
        total=Sum('paid_amount')
    )['total'] or 0

    daily_sales_today = TrainingRegistration.objects.filter(
        date__date=today,
        paid_amount__isnull=False
    ).aggregate(total=Sum('paid_amount'))['total'] or 0

    daily_sales_yesterday = TrainingRegistration.objects.filter(
        date__date=yesterday,
        paid_amount__isnull=False
    ).aggregate(total=Sum('paid_amount'))['total'] or 0

    percent_change = ((daily_sales_today - daily_sales_yesterday) / daily_sales_yesterday * 100
                      if daily_sales_yesterday > 0 else (100 if daily_sales_today > 0 else 0))

    current_date = localtime(now()).strftime('%B %d, %Y')

    payment_qs = TrainingPayment.objects.select_related('registration')
    payment_map = {p.registration_id: p for p in payment_qs if p.registration_id is not None}

    overviews = TrainingRegistration.objects.prefetch_related(
        Prefetch(
            'students',
            queryset=TrainingStudentDetail.objects.order_by('id'),
            to_attr='ordered_students'
        )
    ).order_by('-team_id')

    transactions = (
        TrainingPayment.objects
        .select_related('registration')
        .prefetch_related(
            Prefetch(
                'registration__students',
                queryset=TrainingStudentDetail.objects.order_by('id'),
                to_attr='ordered_students'
            )
        )
        .filter(registration__isnull=False)
        .order_by('-registration__team_id')[:10]
    )

    return render(request, 'admin/training/sales_payment.html', {
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
def update_project(request):
    if request.method == "POST":
        profile = getattr(request.user, "profile", None)
        if not request.user.is_superuser and (not profile or profile.role not in ['main_admin', 'developer', 'sales']):
            messages.error(request, "You do not have permission to update this project.")
            return redirect('login')

        project_id = request.POST.get("project_id")
        project = get_object_or_404(TrainingRegistration, id=project_id)

        # Update logic
        project.team_id = request.POST.get("team_id")
        project.name = request.POST.get("name")
        project.contact = request.POST.get("contact")
        project.whatsapp_no = request.POST.get("whatsapp_no")
        project.email = request.POST.get("email")
        project.college_name = request.POST.get("college") or project.college_name
        project.degree = request.POST.get("degree") or project.degree
        project.department = request.POST.get("department")
        project.domain = request.POST.get("domain")
        project.duration = request.POST.get("duration")
        project.training_mode = request.POST.get("training_mode")
        project.staff_name = request.POST.get("staff_name")

        project.save()
        messages.success(request, "Project updated successfully.")

        # Role-based redirection
        if request.user.is_superuser or profile.role == 'main_admin':
            return redirect('admin_training:registration')
        elif profile.role == 'developer':
            return redirect('admin_training:developer_dashboard')
        elif profile.role == 'sales':
            return redirect('admin_training:sales_registration')
        else:
            return redirect('login')

@login_required
def delete_project(request):
    if request.method == "POST":
        profile = getattr(request.user, "profile", None)
        if not request.user.is_superuser and (not profile or profile.role != 'main_admin'):
            messages.error(request, "Only the Main Admin can delete projects.")
            return redirect('admin_training:registration')

        project = get_object_or_404(TrainingRegistration, id=request.POST.get('project_id'))
        project.delete()
        messages.success(request, "Project deleted successfully.")
        return redirect('admin_training:registration')



@login_required
def update_payment(request):
    if request.method == "POST":
        profile = getattr(request.user, "profile", None)
        if not request.user.is_superuser and (not profile or profile.role not in ['main_admin', 'developer', 'sales']):
            messages.error(request, "You do not have permission to update this project.")
            return redirect('login')

        project_id = request.POST.get("project_id")
        project = get_object_or_404(TrainingRegistration, id=project_id)

        #  Directly update only the required 5 fields
        project.domain = request.POST.get("domain")

        try:
            total_amount = float(request.POST.get("total_amount") or 0)
            paid_amount = float(request.POST.get("paid_amount") or 0)
        except ValueError:
            messages.error(request, "Invalid amount entered.")
            return redirect('admin_training:payment')

        balance_amount = max(0, total_amount - paid_amount)

        project.total_amount = total_amount
        project.paid_amount = paid_amount
        project.balance_amount = balance_amount

        project.save()
        messages.success(request, "Payment details updated successfully.")

        # Role-based redirection
        if request.user.is_superuser or profile.role == 'main_admin':
            return redirect('admin_training:payment')
        elif profile.role == 'developer':
            return redirect('admin_training:developer_dashboard')
        elif profile.role == 'sales':
            return redirect('admin_training:sales_payment')
        else:
            return redirect('login')

    messages.error(request, "Invalid request method.")
    return redirect('admin_training:payment')


@login_required
def delete_payment(request):
    if request.method == "POST":
        profile = getattr(request.user, "profile", None)
        if not request.user.is_superuser and (not profile or profile.role != 'main_admin'):
            messages.error(request, "Only the Main Admin can delete projects.")
            return redirect('admin_training:registration')

        project = get_object_or_404(TrainingRegistration, id=request.POST.get('project_id'))
        project.delete()
        messages.success(request, "Project deleted successfully.")
        return redirect('admin_training:payment')
    



@login_required
def sales_accept_payment(request):
    if request.method != 'POST':
        messages.error(request, "Invalid request method.")
        return redirect('admin_training:sales_dashboard')

    payment_id = request.POST.get('payment_id')
    amount = request.POST.get('amount')

    if not payment_id or not amount:
        messages.error(request, "Missing payment details.")
        return redirect('admin_training:sales_dashboard')

    try:
        amount = Decimal(amount)
    except (InvalidOperation, TypeError):
        messages.error(request, "Invalid amount entered.")
        return redirect('admin_training:sales_dashboard')
    
    if amount <= 0:
        messages.error(request, "Payment amount must be greater than zero.")
        return redirect('admin_training:sales_dashboard')

    payment = get_object_or_404(TrainingPayment, id=payment_id)
    registration = payment.registration


    cashpay_id = generate_cashpay_id(payment.bill_no)
    if not cashpay_id:
        messages.error(request, "Invalid bill number. Could not generate cash payment ID.")
        return redirect('admin_training:sales_dashboard')

    # Update Payment details
    payment.cashfree_order_id = cashpay_id
    payment.cashfree_payment_id = cashpay_id
    payment.cashfree_status = 'PAID'
    payment.selected_payment_method = 'cash'
    payment.payment_status = 'success'
    payment.paid = True
    payment.bank = 'N/A'
    payment.save()

    if registration:
        # Generate team_id if not exists
        if not registration.team_id:
            registration.team_id = generate_team_id()
            registration.save()

            # Send confirmation email
            send_payment_email_training(payment, registration)
            return redirect('training:success', payment_id=cashpay_id)

        # Update paid and balance amounts
        registration.paid_amount = (registration.paid_amount or Decimal('0.00')) + amount

        if registration.total_amount:
            registration.balance_amount = registration.total_amount - registration.paid_amount
        else:
            registration.balance_amount = 0

        registration.save()

        send_payment_email_training(payment, registration)
        

    messages.success(request, "Payment processed and email sent successfully.")
    return redirect('admin_training:sales_dashboard')


@login_required
def sales_decline_payment(request):
    if request.method == 'POST':
        payment_id = request.POST.get('payment_id')
        decline_reason = request.POST.get('decline_reason')
        payment = get_object_or_404(TrainingPayment, id=payment_id)

        payment.payment_status = 'failed'
        payment.decline_reason = decline_reason
        payment.save()

        registration = payment.registration
        # Send failure email for cash declines
        if registration:
            send_failure_email_training(payment, registration)

        messages.info(request, f"Payment from {payment.name} has been declined and email sent.")
    else:
        messages.error(request, "Invalid request.")
    return redirect('admin_training:sales_dashboard')




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
            return redirect('admin_training:sales_dashboard')

        # Update Payment Table
        payment = get_object_or_404(TrainingPayment, id=payment_id)
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
            first_student = TrainingStudentDetail.objects.filter(registration=registration).first()
            if first_student:
                first_student.student_name = name.split()[0]  # Just first name
                first_student.email_id = email
                first_student.contact_no = phone
                first_student.save()

        messages.success(request, f"Payment and related records updated successfully for {name}.")
    else:
        messages.error(request, "Invalid request.")

    return redirect('admin_training:sales_dashboard')




