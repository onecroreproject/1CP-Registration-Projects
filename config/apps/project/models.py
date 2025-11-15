from django.db import models
from datetime import datetime
import uuid

class ProjectRegistration(models.Model):

    date = models.DateTimeField(auto_now_add=True)

    team_id = models.CharField(max_length=50, null=True, blank=True)
    delivery_date = models.DateField(null=True, blank=True)

    name = models.TextField(null=True, blank=True)
    contact = models.TextField(null=True, blank=True)
    whatsapp_no = models.TextField(null=True, blank=True)
    email = models.TextField(null=True, blank=True)

    college_name = models.CharField(max_length=255)
    degree = models.CharField(max_length=255, null=True, blank=True)
    department = models.CharField(max_length=255, null=True, blank=True)
    domain = models.CharField(max_length=255)
    topic = models.CharField(max_length=255, null=True, blank=True)

    reference_details = models.TextField(max_length=255, null=True, blank=True)
    workflow_abstract = models.CharField(max_length=20, null=True, blank=True)
    ppt_file = models.CharField(max_length=20, null=True, blank=True)
    output_video = models.CharField(max_length=20, null=True, blank=True)
    source_code = models.CharField(max_length=20, null=True, blank=True)
    complete_document = models.CharField(max_length=20, null=True, blank=True)
    explanation_file = models.CharField(max_length=20, null=True, blank=True)

    payment_option = models.CharField(max_length=100, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    balance_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    delivery_status = models.CharField(max_length=100, null=True, blank=True)
    project_status = models.CharField(max_length=100, null=True, blank=True)
    developer_name = models.CharField(max_length=255, null=True, blank=True)
    delivery_person_name = models.CharField(max_length=255, null=True, blank=True)
    reason = models.TextField(null=True, blank=True)

    invoice_number = models.CharField(max_length=100, null=True, blank=True)
    invoice_pdf = models.FileField(upload_to='invoices/', null=True, blank=True)

    @property
    def latest_bill_no(self):
        latest_payment = self.projectpayment_set.order_by('-created_at').first()
        return latest_payment.bill_no if latest_payment else ''




class ProjectStudentDetail(models.Model):
    registration = models.ForeignKey(ProjectRegistration, on_delete=models.CASCADE, related_name='students')
    student_name = models.CharField(max_length=255)
    email_id = models.EmailField()
    contact_no = models.CharField(max_length=15)   
    whatsapp_no = models.CharField(max_length=15)  



class ProjectPayment(models.Model):
    registration = models.ForeignKey(ProjectRegistration, null=True, blank=True, on_delete=models.SET_NULL)
    name = models.TextField()  
    email = models.TextField() 
    phone = models.TextField() 
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Amount in INR rupees (e.g., 100.00)")
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    razorpay_status = models.CharField(max_length=50, blank=True, null=True)  
    razorpay_method = models.CharField(max_length=50, blank=True, null=True)  
    razorpay_contact = models.CharField(max_length=15, blank=True, null=True) 
    razorpay_description = models.TextField(blank=True, null=True)
    bank = models.CharField(max_length=100, blank=True, null=True)
    paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    decline_reason = models.TextField(blank=True, null=True)

    selected_payment_method = models.CharField(max_length=10, null=True, blank=True)
    payment_status = models.CharField(max_length=10, choices=[('success', 'Success'), ('failed', 'Failed')], null=True, blank=True)

    selected_payment_option = models.CharField(max_length=50,choices=[('Advance', 'Advance'), ('Full', 'Full')],null=True,blank=True)

    bill_no = models.CharField(max_length=10, unique=True, null=True, blank=True)

    @property
    def amount_rupees(self):
        return self.amount

    def save(self, *args, **kwargs):
        if not self.bill_no:
            current_year = datetime.now().year
            payments_this_year = ProjectPayment.objects.filter(created_at__year=current_year).order_by('-created_at')

            if payments_this_year.exists() and payments_this_year.first().bill_no:
                last_number = int(payments_this_year.first().bill_no[1:])
                new_number = last_number + 1
            else:
                new_number = 1

            self.bill_no = f"B{new_number:05d}"

        super().save(*args, **kwargs)

