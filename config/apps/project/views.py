from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.utils import timezone
from apps.project.models import ProjectRegistration, ProjectStudentDetail, ProjectPayment
from apps.admin_module.models import Domain
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
import razorpay
from django.conf import settings
from django.core.mail import EmailMessage
from io import BytesIO
from reportlab.pdfgen import canvas
from datetime import datetime
from reportlab.pdfgen import canvas
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.urls import reverse
from django.http import Http404
import json
import random
from django.core.mail import send_mail
from django.db.models import Q

import os
from io import BytesIO
from django.core.mail import EmailMessage
from django.conf import settings
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

from django.http import JsonResponse, HttpResponseBadRequest

from django.contrib.admin.views.decorators import staff_member_required
from django.core.files.base import ContentFile
import re
from django.utils.timezone import now
from decimal import Decimal


from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def dashboard_view(request):
    total_ids = ProjectRegistration.objects.filter(
        Q(team_id__isnull=False) & ~Q(team_id__exact='')
    ).count()

    return render(request, 'admin_project:project.html', {
        'total_ids': total_ids,
    })


@staff_member_required
def custom_admin_dashboard(request):
    return render(request, 'admin/custom_dashboard.html')




def home(request):
    return render(request, 'project/home.html')

def users(request):
    return render(request, 'project/users.html')

def existing_user_view(request):
    return render(request, 'project/existing_user.html')


def generate_team_id():
    current_year_short = datetime.now().strftime("%y")

    last_payment = ProjectPayment.objects.filter(registration__team_id__startswith=f"1CP{current_year_short}/").order_by('-registration__team_id').first()

    if last_payment and last_payment.registration.team_id:
        match = re.search(r'/(\d+)$', last_payment.registration.team_id)
        last_number = int(match.group(1)) if match else 0
    else:
        last_number = 0

    next_id = last_number + 1
    return f"1CP{current_year_short}/{next_id:05d}"


@csrf_exempt
def terms_view(request):
    if request.method == 'POST':
        if request.POST.get('agree_terms'):
            return redirect('project:registration_form')
        else:
            messages.error(request, 'You must agree to the terms and conditions to proceed.')
    return render(request, 'project/terms.html')

@csrf_exempt
def terms_exist(request):
    if request.method == 'POST':
        if request.POST.get('agree_terms'):
            return redirect('project:existing_user')
        else:
            messages.error(request, 'You must read to the instructions to proceed.')
    return render(request, 'project/terms_exist.html')


@csrf_exempt
def registration_form_view(request):
    if request.method == 'POST':
        try:
            # Step 1: Extract posted data
            college_name = request.POST.get('college_name', '').strip()
            degree = request.POST.get('degree', '').strip()
            department = request.POST.get('department', '').strip()
            domain = request.POST.get('domain', '').strip()
            topic = request.POST.get('topic') or None
            reference_details = request.POST.get('reference_details') or None
            payment_option = request.POST.get('payment_option', 'Registration').strip()
            num_members = int(request.POST.get('num_members', 0))

            paid_amount = Decimal(request.POST.get('paid_amount') or 0.0)
            total_amount = Decimal(request.POST.get('total_amount') or 0.0)
            balance_amount = Decimal(request.POST.get('balance_amount') or 0.0)

            if not college_name or not degree or not domain or num_members < 1:
                raise ValueError("Please fill all required fields.")

            # Step 2: Create initial ProjectRegistration (names to be updated later)
            registration = ProjectRegistration.objects.create(
                college_name=college_name,
                degree=degree,
                department=department,
                domain=domain,
                topic=topic,
                reference_details=reference_details,
                payment_option=payment_option,
                total_amount=total_amount,
                paid_amount=paid_amount,
                balance_amount=balance_amount,
            )

            # Step 3: Add student details
            names = []
            contacts = []
            whatsapp_nos = []
            emails = []

            for i in range(1, num_members + 1):
                student_name = request.POST.get(f'student_name_{i}', '').strip()
                email_id = request.POST.get(f'student_email_{i}', '').strip()
                contact_no = request.POST.get(f'student_contact_{i}', '').strip()
                whatsapp_no = request.POST.get(f'student_whatsapp_{i}', '').strip()

                if not student_name or not email_id or not contact_no:
                    raise ValueError(f"Missing required details for Student {i}")

                ProjectStudentDetail.objects.create(
                    registration=registration,
                    student_name=student_name,
                    email_id=email_id,
                    contact_no=contact_no,
                    whatsapp_no=whatsapp_no
                )

                names.append(student_name)
                contacts.append(contact_no)
                whatsapp_nos.append(whatsapp_no)
                emails.append(email_id)

            # Step 4: Update ProjectRegistration with combined student details
            registration.name = '\n'.join(names)
            registration.contact = '\n'.join(contacts)
            registration.whatsapp_no = '\n'.join(whatsapp_nos)
            registration.email = '\n'.join(emails)
            registration.save()

            # Step 5: Store payment info in session
            request.session['payment_type'] = payment_option
            request.session['payment_amount'] = str(paid_amount)
            request.session['registration_id'] = registration.id

            messages.success(request, "Registration successful. Proceed to payment.")
            return redirect('project:choose_payment_option', registration_id=registration.id)

        except Exception as e:
            messages.error(request, f"Registration failed: {str(e)}")
            print("[ERROR]", str(e))

    return render(request, 'project/registration_form.html', {  
        'member_range': range(1, 11),
        'domains': Domain.objects.all(),
    })


client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))




@csrf_exempt
def payment_update(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        payment_id = data.get('payment_id')
        order_id = data.get('order_id')
        signature = data.get('signature')

        try:
            # Optional: Verify signature
            params_dict = {
                'razorpay_order_id': order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            }
            client.utility.verify_payment_signature(params_dict)

            payment = ProjectPayment.objects.get(razorpay_order_id=order_id)
            payment.razorpay_payment_id = payment_id
            payment.razorpay_signature = signature
            payment.paid = True
            payment.save()

            return JsonResponse({
                'status': 'success',
                'redirect_url':  f"{reverse('project:processing_view')}?payment_id={payment_id}"
            })
        except ProjectPayment.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Order not found'})
        except razorpay.errors.SignatureVerificationError:
            return JsonResponse({'status': 'error', 'message': 'Invalid signature'})
    return JsonResponse({'status': 'error', 'message': 'Invalid method'})



@csrf_exempt
def charge_view(request):
    if request.method == 'POST':
        try:
            # Get the latest registration
            registration_data = ProjectRegistration.objects.order_by('-id').first()

            if not registration_data:
                return render(request, 'error.html', {'message': 'No registration data found.'})

            amount_in_paisa = int(registration_data.paid_amount * 100)

            # Get payment ID from POST request
            payment_id = request.POST.get('razorpay_payment_id')

            # Fetch payment details from Razorpay
            payment_data = client.payment.fetch(payment_id)
            authorized_amount = payment_data['amount']

            if amount_in_paisa != authorized_amount:
                return render(request, 'error.html', {
                    'message': f"Authorized amount ({authorized_amount}) does not match expected amount ({amount_in_paisa})."
                })

            # Capture payment
            client.payment.capture(payment_id, amount_in_paisa)

            # Redirect to success page
            return redirect('success')  # Make sure you have a 'success' URL pattern
        except Exception as e:
            return render(request, 'project/error.html', {'message': f"Payment failed: {e}"})

    return HttpResponse("Invalid request method", status=405)

@csrf_exempt
def processing_view(request):
    payment_id = request.GET.get('payment_id')
    return render(request, 'project/processing.html', {'payment_id': payment_id})



@csrf_exempt
def success_view(request, payment_id):
    try:
        # Fetch the payment using the given razorpay_payment_id (or cashpay_id)
        payment = ProjectPayment.objects.filter(razorpay_payment_id=payment_id).order_by('-id').first()
        registration = payment.registration
        

        #  CASH PAYMENT HANDLING
        if payment.selected_payment_method == 'cash':
            # Mark as paid if not already
            if not payment.paid:
                payment.paid = True
                payment.razorpay_status = 'captured'  # Treat as success
                payment.save()

            # Generate team_id if not already
            if registration and not registration.team_id:
                registration.team_id = generate_team_id()
                registration.save()

            # Send confirmation email
            send_payment_email_django(payment, registration)

            return render(request, 'project/success.html', {
                'payment': payment,
                'registration': registration,
                'payment_id': payment_id,
                'payment_mode': 'Cash',
                'user_role': request.user.profile.role if request.user.is_authenticated else None
            })

        #  ONLINE PAYMENT (Razorpay)
        razorpay_payment = client.payment.fetch(payment_id)
        status = razorpay_payment.get('status')

        payment.razorpay_status = status
        payment.razorpay_method = razorpay_payment.get('method')
        payment.razorpay_contact = razorpay_payment.get('contact')
        payment.razorpay_description = razorpay_payment.get('description')
        payment.bank = razorpay_payment.get('bank') or 'N/A'
        payment.paid = (status == 'captured')
        payment.save()

        if status == 'captured':
            if registration and not registration.team_id:
                registration.team_id = generate_team_id()
                registration.save()
            else:
                registration.paid_amount = (registration.paid_amount or Decimal('0.00')) + payment.amount

            if registration.total_amount:
                registration.balance_amount = registration.total_amount - registration.paid_amount
            else:
                registration.balance_amount = 0

            registration.save()

            send_payment_email_django(payment, registration)

            return render(request, 'project/success.html', {
                'payment': payment,
                'registration': registration,
                'payment_id': payment_id,
                'payment_mode': 'Online',
                'user_role': request.user.profile.role if request.user.is_authenticated else None
            })
        else:
            return render(request, 'project/error.html', {
                'message': 'Payment not completed. Please try again or contact support.',
                'payment_status': status
            })

    except ProjectPayment.DoesNotExist:
        return render(request, 'project/error.html', {'message': 'Invalid payment ID. Please contact support.'})

    except razorpay.errors.BadRequestError:
        return render(request, 'project/error.html', {'message': 'Invalid request to Razorpay. Please contact support.'})

    except Exception as e:
        return render(request, 'project/error.html', {'message': f'Unexpected error: {e}'})

    

    
def send_payment_email_django(payment, registration):
    try:
        subject = f"Payment Confirmation - Team ID: {registration.team_id}"
        recipient = payment.email

        logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', '1croreprojects_logo.jpg')

        buffer = BytesIO()
        width, height = A4
        pdf = canvas.Canvas(buffer, pagesize=A4)

        # === TEXT WATERMARK ===
        pdf.saveState()
        pdf.setFillColorRGB(0.6, 0.6, 0.6)
        pdf.setFont("Helvetica-Bold", 60)
        pdf.translate(width/2, height/2)
        pdf.rotate(45)
        pdf.setFillAlpha(0.5)
        pdf.drawCentredString(0, 0, "PAID")
        pdf.restoreState()

        # === HEADER WITH GREEN BACKGROUND ===
        header_height = 40
        pdf.setFillColorRGB(1, 1, 1)  
  
        pdf.rect(0, height - header_height + 5, width, header_height, fill=True, stroke=False)

        pdf.setFillColorRGB(0, 0, 0) 
        pdf.setFont("Helvetica-Bold", 20)
 
        pdf.drawCentredString(width / 2, height - 50, "INVOICE")
       
        y_pos = height - header_height - 40  

        top_y = height - 100  
        line_spacing = 15     
        line_height_below = 1 

        # === Logo on the Left ===
        logo_width = 110
        logo_height = 110
        logo_y = height - 160  

        if os.path.exists(logo_path):
            pdf.drawImage(logo_path, 40, logo_y, width=logo_width, height=logo_height, preserveAspectRatio=True, mask='auto')
        else:
            print("Logo not found")

        pdf.setFont("Helvetica", 10)
        text_y_1 = top_y - 10               
        text_y_2 = text_y_1 - line_spacing  

        pdf.drawRightString(width - 40, text_y_1, f"Invoice No.: 1CP-INV-{payment.id:05d}")
        pdf.drawRightString(width - 40, text_y_2, f"Date: {payment.created_at.strftime('%Y-%m-%d')}")

        content_bottom_y = min(logo_y, text_y_2)  
        line_y = content_bottom_y - line_height_below

        pdf.setLineWidth(0.5)
        pdf.setStrokeColorRGB(0, 0, 0)  
        pdf.line(40, line_y, width - 40, line_y)

        # === BILLED TO (LEFT) ===
        y = height - 220
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(40, y, "Billed To")

        pdf.setFont("Helvetica", 10)
        pdf.drawString(40, y - 25, f"Form ID: {registration.team_id}")
        pdf.drawString(40, y - 43, f"College: {registration.college_name}")
        pdf.drawString(40, y - 61, f"Degree: {registration.degree}")
        pdf.drawString(40, y - 79, f"Domain: {registration.domain}")

        # === PAYMENT DETAILS (RIGHT) ===
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawRightString(width - 40, y, "Payment Details")
        pdf.setFont("Helvetica", 10)
        
        payment_mode = payment.selected_payment_method.capitalize() if payment.selected_payment_method else 'N/A'
        payment_type = payment.selected_payment_option.capitalize() if payment.selected_payment_option else 'N/A'
        payment_id_value = payment.razorpay_payment_id if payment.razorpay_payment_id else 'Cash Payment'

        pdf.drawRightString(width - 40, y - 25, f"Payment ID: {payment_id_value}")
        pdf.drawRightString(width - 40, y - 43, f"Payment Option: {payment_type}")
        pdf.drawRightString(width - 40, y - 61, f"Payment Mode: {payment_mode}")

        # Update y for next section (like student table)
        y = y - 120

        team_id = registration.team_id

        team_registrations = ProjectRegistration.objects.filter(team_id=team_id)

        student_names = ProjectStudentDetail.objects.filter(
            registration__in=team_registrations
        ).values_list('student_name', flat=True)

        # Add serial numbers (1., 2., etc.)
        if student_names:
            combined_names = "<br/>".join(f"{i+1}. {name}" for i, name in enumerate(student_names))
        else:
            combined_names = payment.name


        topic = registration.topic or "Not Mentioned"
        total_amount = registration.total_amount or Decimal('0.00')
        paid_amount = registration.paid_amount or Decimal('0.00')
        balance_amount = max(Decimal('0.00'), total_amount - paid_amount)


        # Create styles
        styles = getSampleStyleSheet()

        # Left-aligned style for student names
        style_left = ParagraphStyle(name='LeftAlign')
        style_left.alignment = 0  # LEFT
        style_left.wordWrap = 'CJK'

        # Centered style for topic
        style_centered = ParagraphStyle(name='CenterAlign')
        style_centered.alignment = 1  # CENTER
        style_centered.wordWrap = 'CJK'

        # Wrap both name and topic
        wrapped_names = Paragraph(combined_names, style_left)
        wrapped_topic = Paragraph(topic, style_centered)

        data = [
            ['Student Name(s)', 'Project Topic', 'Total Amount', 'Paid Amount', 'Balance Amount'],
            [wrapped_names, wrapped_topic, f"Rs.{total_amount:.2f}", f"Rs.{paid_amount:.2f}", f"Rs.{balance_amount:.2f}"]
        ]

       
        table = Table(data, colWidths=[100, 130, 100, 100, 100])  
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.green),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),  
            ('ALIGN', (0, 1), (0, 1), 'LEFT'),  
            ('ALIGN', (2, 1), (-1, 1), 'CENTER'),  
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))

        table_width, table_height = table.wrap(0, 0)

        
        table.drawOn(pdf, 40, y - table_height)        

        # === Footer (Centered) ===
        y = y - table_height - 40  
        pdf.setFont("Helvetica-Oblique", 10)
        pdf.drawCentredString(width / 2, y, "This is a computer-generated invoice. No signature or seal required.")
        y -= 20
        pdf.setFont("Helvetica-Bold", 12)
        pdf.setFillColorRGB(0, 0.5, 0)  
        pdf.drawCentredString(width / 2, y, "Thank You!")


        # === Footer (Centered Line and Address) ===
        footer_y = 60  # 60 pts from bottom

        # Footer line above address
        pdf.setLineWidth(0.7)
        pdf.setStrokeColorRGB(0, 0, 0)
        pdf.line(50, footer_y + 70, width - 50, footer_y + 70)

        center_x = width / 2

        # Footer text (all centered)
        pdf.setFont("Helvetica-Bold", 12)
        pdf.setFillColorRGB(0, 0, 0)
        pdf.drawCentredString(center_x, footer_y + 45, "1CroreProjects")

        pdf.setFont("Helvetica", 9)
        pdf.drawCentredString(center_x, footer_y + 30, "No - 68/70, Ground Floor, Raahat Plaza, Near Chroma")
        pdf.drawCentredString(center_x, footer_y + 16, "Vadapalani, Chennai, Tamil Nadu 600026")
        pdf.drawCentredString(center_x, footer_y + 2, "Email: 1croreprojects@gmail.com | Phone: +91-7904320834")
        pdf.drawCentredString(center_x, footer_y - 12, "Website: https://1croreprojects.com/")

        # Finalize the PDF content
        pdf.save()
        buffer.seek(0)

        # === Send Email with PDF attachment ===
        email = EmailMessage(
            subject=subject,
            body=(
                f"Dear {payment.name},\n\n"
                "Thank you for your payment. Please find the attached invoice PDF.\n\n"
                "Best regards,\n1CroreProjects"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        )
        email.attach(f"Invoice_{payment.id}.pdf", buffer.read(), "application/pdf")
        email.send()

        # Reset buffer and save PDF to DB
        buffer.seek(0)
        pdf_content = buffer.read()

        # Generate invoice number
        invoice_number = f"1CP-INV-{payment.id:05d}"

        registration.invoice_number = invoice_number
        registration.invoice_pdf.save(f"invoice_{payment.id}.pdf", ContentFile(pdf_content))
        registration.save()

    except Exception as e:
        print(f"Error sending payment email: {e}")
    
    

def failure_view(request, payment_id):
    try:
        payment = ProjectPayment.objects.get(razorpay_payment_id=payment_id)
        registration = payment.registration

        if payment.selected_payment_method != 'cash':
            razorpay_payment = client.payment.fetch(payment_id)
            payment.razorpay_status = razorpay_payment.get('status')
            payment.razorpay_method = razorpay_payment.get('method')
            payment.razorpay_contact = razorpay_payment.get('contact')
            payment.razorpay_description = razorpay_payment.get('description')
            payment.bank = razorpay_payment.get('bank') or 'N/A'
            payment.paid = payment.razorpay_status == 'captured'
            payment.save()

        if not payment.paid:
            request.session['payment_id'] = payment.id  
            return redirect('payment_failed')  

        return render(request, 'failure.html', {
            'payment': payment,
            'registration': registration,
        })

    except ProjectPayment.DoesNotExist:
        return render(request, 'error.html', {'message': 'Invalid payment ID. Please contact support.'})
    except razorpay.errors.BadRequestError:
        return render(request, 'error.html', {'message': 'Invalid request to Razorpay. Please contact support.'})
    except Exception as e:
        return render(request, 'error.html', {'message': f'Unexpected error: {str(e)}'})
   



def send_failure_email_django(payment, registration):
    try:
        subject = "Payment Failed - 1CroreProjects"
        recipient = payment.email

        logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', '1croreprojects_logo.jpg')

        buffer = BytesIO()
        width, height = A4
        pdf = canvas.Canvas(buffer, pagesize=A4)

        # === TEXT WATERMARK ===
        pdf.saveState()
        pdf.setFillColorRGB(0.6, 0.6, 0.6)
        pdf.setFont("Helvetica-Bold", 60)
        pdf.translate(width/2, height/2)
        pdf.rotate(45)
        pdf.setFillAlpha(0.5)
        pdf.drawCentredString(0, 0, "FAILED")
        pdf.restoreState()

        # === HEADER WITH GREEN BACKGROUND ===
        header_height = 40
        pdf.setFillColorRGB(1, 1, 1)  
  
        pdf.rect(0, height - header_height + 5, width, header_height, fill=True, stroke=False)

        pdf.setFillColorRGB(0, 0, 0) 
        pdf.setFont("Helvetica-Bold", 20)
 
        pdf.drawCentredString(width / 2, height - 50, "FAILED PAYMENT INVOICE")
       
        y_pos = height - header_height - 40  

        top_y = height - 100  
        line_spacing = 15     
        line_height_below = 1 

        # === Logo on the Left ===
        logo_width = 110
        logo_height = 110
        logo_y = height - 160  

        if os.path.exists(logo_path):
            pdf.drawImage(logo_path, 40, logo_y, width=logo_width, height=logo_height, preserveAspectRatio=True, mask='auto')
        else:
            print("Logo not found")

        pdf.setFont("Helvetica", 10)
        text_y_1 = top_y - 10               
        text_y_2 = text_y_1 - line_spacing  

        pdf.drawRightString(width - 40, text_y_1, f"1CP_INV_00000")
        pdf.drawRightString(width - 40, text_y_2, f"Date: {payment.created_at.strftime('%Y-%m-%d')}")

        content_bottom_y = min(logo_y, text_y_2)  
        line_y = content_bottom_y - line_height_below

        pdf.setLineWidth(0.5)
        pdf.setStrokeColorRGB(0, 0, 0)  
        pdf.line(40, line_y, width - 40, line_y)

        # === BILLED TO (LEFT) ===
        y = height - 220
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(40, y, "Billed To")

        pdf.setFont("Helvetica", 10)
        pdf.drawString(40, y - 25, f"Form ID: {registration.team_id}")
        pdf.drawString(40, y - 43, f"College: {registration.college_name}")
        pdf.drawString(40, y - 61, f"Degree: {registration.degree}")
        pdf.drawString(40, y - 79, f"Domain: {registration.domain}")

        # === PAYMENT DETAILS (RIGHT) ===
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawRightString(width - 40, y, "Payment Details")
        pdf.setFont("Helvetica", 10)
        
        payment_mode = payment.selected_payment_method.capitalize() if payment.selected_payment_method else 'N/A'
        payment_type = payment.selected_payment_option.capitalize() if payment.selected_payment_option else 'N/A'
        payment_id_value = payment.razorpay_payment_id if payment.razorpay_payment_id else 'Cash Payment'

        pdf.drawRightString(width - 40, y - 25, f"Payment ID: {payment_id_value}")
        pdf.drawRightString(width - 40, y - 43, f"Payment Option: {payment_type}")
        pdf.drawRightString(width - 40, y - 61, f"Payment Mode: {payment_mode}")

        # Update y for next section (like student table)
        y = y - 120

        team_id = registration.team_id

        team_registrations = ProjectRegistration.objects.filter(team_id=team_id)

        student_names = ProjectStudentDetail.objects.filter(
            registration=registration
        ).values_list('student_name', flat=True)

        # Add serial numbers (1., 2., etc.)
        if student_names:
            combined_names = "<br/>".join(f"{i+1}. {name}" for i, name in enumerate(student_names))
        else:
            combined_names = payment.name


        topic = registration.topic or "Not Mentioned"
        total_amount = registration.total_amount or Decimal('0.00')
        paid_amount = registration.paid_amount or Decimal('0.00')
        balance_amount = max(Decimal('0.00'), total_amount - paid_amount)


        # Create styles
        styles = getSampleStyleSheet()

        # Left-aligned style for student names
        style_left = ParagraphStyle(name='LeftAlign')
        style_left.alignment = 0  # LEFT
        style_left.wordWrap = 'CJK'

        # Centered style for topic
        style_centered = ParagraphStyle(name='CenterAlign')
        style_centered.alignment = 1  # CENTER
        style_centered.wordWrap = 'CJK'

        # Wrap both name and topic
        wrapped_names = Paragraph(combined_names, style_left)
        wrapped_topic = Paragraph(topic, style_centered)

        data = [
            ['Student Name(s)', 'Project Topic', 'Total Amount', 'Paid Amount', 'Balance Amount'],
            [wrapped_names, wrapped_topic, f"Rs.{total_amount:.2f}", f"Rs.{paid_amount:.2f}", f"Rs.{balance_amount:.2f}"]
        ]

       
        table = Table(data, colWidths=[100, 130, 100, 100, 100])  
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.green),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),  
            ('ALIGN', (0, 1), (0, 1), 'LEFT'),  
            ('ALIGN', (2, 1), (-1, 1), 'CENTER'),  
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))

        table_width, table_height = table.wrap(0, 0)

        
        table.drawOn(pdf, 40, y - table_height)        

        # === Footer (Centered) ===
        y = y - table_height - 40  
        pdf.setFont("Helvetica-Oblique", 10)
        pdf.drawCentredString(width / 2, y, "This is a computer-generated invoice. No signature or seal required.")
        y -= 20
        pdf.setFont("Helvetica-Bold", 12)
        pdf.setFillColorRGB(0, 0.5, 0)  
        pdf.drawCentredString(width / 2, y, "Thank You!")


        # === Footer (Centered Line and Address) ===
        footer_y = 60  # 60 pts from bottom

        # Footer line above address
        pdf.setLineWidth(0.7)
        pdf.setStrokeColorRGB(0, 0, 0)
        pdf.line(50, footer_y + 70, width - 50, footer_y + 70)

        center_x = width / 2

        # Footer text (all centered)
        pdf.setFont("Helvetica-Bold", 12)
        pdf.setFillColorRGB(0, 0, 0)
        pdf.drawCentredString(center_x, footer_y + 45, "1CroreProjects")

        pdf.setFont("Helvetica", 9)
        pdf.drawCentredString(center_x, footer_y + 30, "No - 68/70, Ground Floor, Raahat Plaza, Near Chroma")
        pdf.drawCentredString(center_x, footer_y + 16, "Vadapalani, Chennai, Tamil Nadu 600026")
        pdf.drawCentredString(center_x, footer_y + 2, "Email: 1croreprojects@gmail.com | Phone: +91-7904320834")
        pdf.drawCentredString(center_x, footer_y - 12, "Website: https://1croreprojects.com/")

        # Finalize the PDF content
        pdf.save()
        buffer.seek(0)

        # === Send Email with PDF attachment ===
        email = EmailMessage(
            subject=subject,
            body=(
                f"Dear {payment.name},\n\n"
                "We regret to inform you that your recent payment attempt was not completed successfully.\n"
                "If any amount was deducted from your account, it will be refunded automatically by the payment gateway.\n\n"
                "Registration Details:\n"
                f"Name: {payment.name}\n"
                f"Email: {payment.email}\n"
                f"Phone: {payment.phone}\n"
                f"Amount Attempted: ₹{payment.amount}\n\n"
                "Please try the payment again at your convenience. If you continue to face issues, feel free to contact our support team.\n\n"
                "Best regards,\n"
                "1CroreProjects"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        )
        email.attach(f"Invoice_{payment.id}.pdf", buffer.read(), "application/pdf")
        email.send()

        # Reset buffer and save PDF to DB
        buffer.seek(0)
        pdf_content = buffer.read()

        # Generate invoice number
        invoice_number = f"1CP_INV_00000"

        registration.invoice_number = invoice_number
        registration.invoice_pdf.save(f"invoice_{payment.id}.pdf", ContentFile(pdf_content))
        registration.save()

    except Exception as e:
        print(f"Error sending payment email: {e}")

        

OTP_STORE = {}  # temp in-memory storage

@csrf_exempt
def send_otp(request):
    if request.method == "POST":
        data = json.loads(request.body)
        email = data.get("email")
        otp = str(random.randint(100000, 999999))
        OTP_STORE[email] = otp

        # Send OTP via email
        send_mail(
            'Your OTP Code',
            f'Your OTP code is {otp}',
            'your_email@example.com',
            [email],
            fail_silently=False,
        )

        return JsonResponse({'status': 'sent'})
    

@csrf_exempt
def verify_otp(request):
    if request.method == "POST":
        data = json.loads(request.body)
        email = data.get("email")
        otp = data.get("otp")

        if OTP_STORE.get(email) == otp:
            del OTP_STORE[email]
            # Save verified email in session for later use
            request.session['otp_verified_email'] = email
            return JsonResponse({'status': 'verified'})
        else:
            return JsonResponse({'status': 'invalid'})

    # For GET request, render the OTP input page (adjust template name accordingly)
    return render(request, 'existing_user.html')




@csrf_exempt
def dashboard_view(request):
    context = {}
    email = request.session.get('otp_verified_email') or request.GET.get('email')

    selected_team_id = None
    selected_registration = None
    error = None

    if not email:
        context['error'] = "Email not found in session or URL."
        return render(request, 'dashboard.html', context)

    # Fetch students using email
    students = ProjectStudentDetail.objects.filter(email_id=email)

    if not students.exists():
        context['not_registered'] = True
        context['email'] = email
        return render(request, 'dashboard.html', context)

    registration_ids = students.values_list('registration_id', flat=True).distinct()

    if request.method == 'POST':
        team_id = request.POST.get('selected_team_id')
        submit_action = request.POST.get('submit_action')

        try:
            reg = ProjectRegistration.objects.get(team_id=team_id)
        except ProjectRegistration.DoesNotExist:
            messages.error(request, "Invalid Team ID.")
            return redirect(f"{request.path}?email={email}")

        if submit_action == 'select_row':
            selected_team_id = team_id
            selected_registration = reg

        elif submit_action == 'update_topic':
            topic_text = request.POST.get('topic_text', '').strip()
            if topic_text:
                reg.topic = topic_text
                reg.save()
                messages.success(request, "Topic updated successfully!")
            else:
                messages.error(request, "Please enter a valid topic.")
            selected_team_id = team_id
            selected_registration = reg

        elif submit_action in ['registration_pay', 'advance_pay', 'full_pay']:
            if submit_action == 'advance_pay':
                request.session['payment_type'] = 'Advance'
                request.session['payment_amount'] = float(request.POST.get('advance_amount', 0))

            elif submit_action == 'full_pay':
                request.session['payment_type'] = 'Full'
                request.session['payment_amount'] = float(reg.balance_amount or 0)

            elif submit_action == 'registration_pay':
                request.session['payment_type'] = 'Registration'
                request.session['payment_amount'] = float(reg.paid_amount or 0)

            request.session['registration_id'] = reg.id
            return redirect('choose_payment_option', registration_id=reg.id)

    overviews = ProjectRegistration.objects.filter(id__in=registration_ids)

    for reg in overviews:
        reg.ordered_students = ProjectStudentDetail.objects.filter(registration=reg).order_by('id')

    context.update({
        'registrations': overviews,
        'email': email,
        'selected_team_id': selected_team_id,
        'selected_registration': selected_registration,
        'error': error,
    })

    return render(request, 'project/dashboard.html', context)




@csrf_exempt
def choose_payment_option(request, registration_id):
    try:
        registration = ProjectRegistration.objects.get(id=registration_id)
    except ProjectRegistration.DoesNotExist:
        messages.error(request, "Invalid registration ID.")
        return redirect('project:registration_form')

    # Get all students
    students = ProjectStudentDetail.objects.filter(registration=registration)
    if not students.exists():
        messages.error(request, "Student details missing.")
        return redirect('project:registration_form')

    # Use the first student for payment
    first_student = students.first()

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        if payment_method not in ['cash', 'online']:
            messages.error(request, "Invalid payment method selected.")
            return redirect('project:choose_payment_option', registration_id=registration_id)

        # Payment amount and option
        payment_option = request.session.get('payment_type', 'Full')  # 'Advance' or 'Full'
        payment_amount = request.session.get('payment_amount') or registration.paid_amount or 0

        # Create payment only for first student
        payment = ProjectPayment.objects.create(
            registration=registration,
            name=first_student.student_name,   
            email=first_student.email_id,
            phone=first_student.contact_no,
            amount=payment_amount,
            selected_payment_method=payment_method,
            selected_payment_option=payment_option,
            created_at=timezone.now()
        )

        # Optionally, update registration with combined info
        registration.name = '\n'.join([s.student_name for s in students])
        registration.contact = '\n'.join([s.contact_no for s in students])
        registration.whatsapp_no = '\n'.join([s.whatsapp_no for s in students])
        registration.email = '\n'.join([s.email_id for s in students])
        registration.save()

        # Clear session
        request.session.pop('payment_type', None)
        request.session.pop('payment_amount', None)

        if payment_method == 'cash':
            return redirect('project:cash_payment', registration_id=registration.id, payment_id=payment.id)

        # Razorpay flow
        amount_paise = int(float(payment.amount) * 100)
        if amount_paise < 100:
            messages.error(request, "Online payment amount must be at least ₹1.")
            payment.delete()
            return redirect('project:choose_payment_option', registration_id=registration.id)

        if not payment.razorpay_order_id:
            order_data = {
                'amount': amount_paise,
                'currency': 'INR',
                'payment_capture': 1
            }
            razorpay_order = client.order.create(data=order_data)
            payment.razorpay_order_id = razorpay_order['id']
            payment.save()
        else:
            razorpay_order = {'id': payment.razorpay_order_id}

        context = {
            'payment_details': {
                'name': payment.name,
                'email': payment.email,
                'phone': payment.phone,
                'amount': amount_paise,
                'amount_rupees': payment.amount
            },
            'razorpay_order_id': razorpay_order['id'],
            'razorpay_key': settings.RAZORPAY_KEY_ID,
            'csrf_token': request.COOKIES.get('csrftoken')
        }

        return render(request, 'project/payment.html', context)

    return render(request, 'project/choose_payment.html', {'registration': registration})





def cash_payment_view(request, registration_id, payment_id):
    registration = get_object_or_404(ProjectRegistration, id=registration_id)

    payment = get_object_or_404(
        ProjectPayment,
        id=payment_id,
        registration=registration,
        selected_payment_method='cash'
    )

    context = {
        'registration': registration,
        'bill_no': payment.bill_no,
        'payment': payment,
    }

    return render(request, 'project/cash.html', context)



def payment_failed_view(request):
    payment_id = request.session.get('payment_id')
    registration_id = request.session.get('registration_id')

    if payment_id:
        try:
            payment = ProjectPayment.objects.get(id=payment_id)
            registration = payment.registration
            send_failure_email_django(payment, registration)
        except ProjectPayment.DoesNotExist:
            pass  # Optionally log
    elif registration_id:
        try:
            registration = ProjectRegistration.objects.get(id=registration_id)
            payment = ProjectPayment.objects.filter(registration=registration).order_by('-id').first()

            if payment:
                send_failure_email_django(payment, registration)
            else:
                # No payment record, construct a dummy one just for email context
                from decimal import Decimal
                dummy_payment = ProjectPayment(
                    name=registration.name,
                    email=registration.email,
                    phone=registration.contact,
                    amount=registration.paid_amount or Decimal("0.00")
                )
                send_failure_email_django(dummy_payment, registration)

        except ProjectRegistration.DoesNotExist:
            pass

    return render(request, 'payment_failed.html')



def index(request):
    return render(request, 'project/index.html')






