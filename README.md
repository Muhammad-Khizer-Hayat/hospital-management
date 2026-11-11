HOSPITAL BILLING UPDATE (version 2)  -  where every file goes
==============================================================

HOW BILLING WORKS NOW
  1. A patient books an appointment (no payment in the booking window).
     Booking creates the appointment and an UNPAID bill for the doctor's fee.
  2. In the patient portal, the appointment row (Appointments page and Dashboard)
     shows a "Pay $150.00" button. The patient picks a payment method there and pays.
     The appointment becomes "confirmed" and the row now shows a "Receipt" button
     that downloads a PDF. The same invoices are in the Billing page.
  3. The admin dashboard > Billing shows every bill (patient, description, status,
     method, receipt number). For an unpaid bill the front desk can press
     "Mark paid" (cash) and download the receipt. Admin > Appointments has a Payment
     column.
  * A doctor with a consultation fee of 0 creates no bill.

HOW TO INSTALL (Windows)
  1. Stop the server (Ctrl+C in the terminal).
  2. BACK UP your project: copy the folder
        E:\MyAI Work\hospital_management
     to another place (for example hospital_management_backup).
  3. Open this extracted folder (hospital_billing_update_v2).
     Select the folders  app  and  frontend  and the file  requirements.txt
  4. Copy them and paste into
        E:\MyAI Work\hospital_management
     When Windows asks, choose "Replace the files in the destination".
     (Folders are merged: only the files listed below are replaced.)
  5. In the terminal, with (venv) active, inside the project folder:
        pip install -r requirements.txt
     (installs reportlab, which makes the PDF receipts)
  6. Start the app:   python run.py
     The new "payments" table is created automatically on start.
  7. Press Ctrl+F5 in the browser on the portal and admin pages.

WHERE EACH FILE GOES   (path inside hospital_management)
  app\models\appointment.py             NEW version  (names + bill info on appointment lists)
  app\models\billing.py                 NEW version  (Payment table, patient name)
  app\schemas\billing.py                NEW version
  app\schemas\appointment.py            NEW version
  app\services\billing_service.py       NEW file     (bills, demo payment, PDF receipt)
  app\services\appointment_service.py   NEW version  (every booking creates an unpaid bill)
  app\services\agent_service.py         NEW version  (phone assistant mentions the fee)
  app\routers\billing.py                NEW version  (pay + receipt download)
  app\routers\appointments.py           NEW version
  frontend\portal.html                  NEW version  (Pay / Receipt buttons on appointments)
  frontend\admin.html                   NEW version  (Billing page with all bills)
  frontend\index.html                   NEW version
  requirements.txt                      NEW version  (adds reportlab==4.2.2)

NOT IN THIS ZIP
  doctors.py, patients.py and schemas\patient.py are not included. If you already
  installed them from the earlier zip, leave them as they are.

TEST IT
  1. Patient: Find Doctors > Book Appointment > Confirm Booking.
  2. Appointments page: the new row has "Pay $..." > choose a method > Pay Now.
  3. The row now shows "Receipt" > click it: a PDF downloads.
  4. Admin: Billing shows the bill; Appointments shows the Payment column.

NOTES
  * Payments are a DEMO: no card data is collected and no real money moves.
    Receipts say "Demo payment" (set DEMO_PAYMENTS = False in
    app\services\billing_service.py to remove that text).
  * Currency symbol is $ (CURRENCY in app\services\billing_service.py).
  * Cancelling an appointment cancels its UNPAID bill. A PAID bill stays paid
    (there is no refund feature yet; the portal warns the patient).
