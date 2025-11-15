from django.db import models
from datetime import datetime

class TrainingRegistration(models.Model):
    date = models.DateTimeField(auto_now_add=True)

    team_id = models.CharField(max_length=50, null=True, blank=True,)

    name = models.TextField(null=True, blank=True)
    contact = models.TextField(null=True, blank=True)
    whatsapp_no = models.TextField(null=True, blank=True)
    email = models.TextField(null=True, blank=True)

    college_name = models.CharField(max_length=255)
    degree = models.CharField(max_length=255, null=True, blank=True)
    department = models.CharField(max_length=255, null=True, blank=True)
    domain = models.CharField(max_length=255)

    reference_details = models.TextField(max_length=255, null=True, blank=True)

    payment_option = models.CharField(max_length=100, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    balance_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    invoice_number = models.CharField(max_length=100, null=True, blank=True)
    invoice_pdf = models.FileField(upload_to='invoices/', null=True, blank=True)

    joining_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    DURATION_CHOICES = [
        ("45_days", "45 days"),
        ("3_months", "3 months"),
        ("6_months", "6 months"),
        ("1_year", "1 year"),
    ]
    duration = models.CharField(max_length=10, choices=DURATION_CHOICES, null=True, blank=True)

    TRAINING_MODE_CHOICES = [
        ("online", "Online"),
        ("offline", "Offline"),
    ]
    training_mode = models.CharField(max_length=20, choices=TRAINING_MODE_CHOICES, null=True, blank=True)

    staff_name = models.CharField(max_length=255, null=True, blank=True)

    @property
    def latest_bill_no(self):
        latest_payment = self.trainingpayment_set.order_by('-created_at').first()
        return latest_payment.bill_no if latest_payment else ''
    
class TrainingStudentDetail(models.Model):
    registration = models.ForeignKey(TrainingRegistration, on_delete=models.CASCADE, related_name='students')
    student_name = models.CharField(max_length=255)
    email_id = models.EmailField()
    contact_no = models.CharField(max_length=20)       
    whatsapp_no = models.CharField(max_length=20) 


class TrainingPayment(models.Model):
    registration = models.ForeignKey(TrainingRegistration, null=True, blank=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15)
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Amount in INR rupees (e.g., 100.00)")

    cashfree_order_id = models.CharField(max_length=200, blank=True, null=True, db_index=True)
    cashfree_payment_id = models.CharField(max_length=200, blank=True, null=True, unique=True)
    cashfree_status = models.CharField(max_length=50, blank=True, null=True)
    cashfree_signature = models.TextField(blank=True, null=True)
    cashfree_order_token = models.TextField(null=True, blank=True)

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
        # Generate bill_no only if not already set
        if not self.bill_no:
            current_year = datetime.now().year

            # Filter payments only for the current year
            payments_this_year = TrainingPayment.objects.filter(created_at__year=current_year).order_by('-created_at')

            if payments_this_year.exists():
                # Extract last number from bill_no like 'B00025'
                last_bill_no = payments_this_year.first().bill_no
                last_number = int(last_bill_no[1:])  # skip 'B'
                new_number = last_number + 1
            else:
                new_number = 1

            self.bill_no = f"B{new_number:05d}"

        super().save(*args, **kwargs)

