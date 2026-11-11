async function loadAppointments() {
  const data = await apiCall('/api/appointments/');
  const container = document.getElementById('appointments-list');
  if (!data || data.length === 0) {
    container.innerHTML = `<div class="empty-state"><div class="empty-icon">📅</div><p>No appointments yet.</p></div>`;
    return;
  }
  container.innerHTML = data.map(a => `
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:start">
        <div>
          <div class="card-title">Dr. Appointment — #${a.id}</div>
          <div class="card-meta">📅 ${new Date(a.appointment_date).toLocaleString()}</div>
          <div class="card-meta" style="margin-top:4px">${a.reason || 'No reason specified'}</div>
        </div>
        <span class="badge badge-${a.status}">${a.status}</span>
      </div>
      ${a.status === 'pending' || a.status === 'confirmed' ? `
        <div style="margin-top:1rem">
          <button class="btn btn-sm btn-danger" onclick="cancelAppt(${a.id})">Cancel</button>
        </div>` : ''}
    </div>
  `).join('');
}

async function loadDoctors() {
  const depts = await apiCall('/api/departments/');
  const doctors = await apiCall('/api/doctors/');
  if (depts) {
    const filter = document.getElementById('dept-filter');
    depts.forEach(d => {
      const opt = document.createElement('option');
      opt.value = d.id; opt.textContent = d.name;
      filter.appendChild(opt);
    });
  }
  renderDoctors(doctors || []);
}

function renderDoctors(doctors) {
  const container = document.getElementById('doctors-list');
  if (!doctors.length) {
    container.innerHTML = `<div class="empty-state"><div class="empty-icon">👨‍⚕️</div><p>No doctors available.</p></div>`;
    return;
  }
  container.innerHTML = doctors.map(d => `
    <div class="doctor-card">
      <div class="doctor-avatar">👨‍⚕️</div>
      <div class="doctor-name">Dr. ${d.user?.full_name || 'N/A'}</div>
      <div class="doctor-spec">${d.specialization || 'General'}</div>
      <div class="doctor-dept">Exp: ${d.experience_years} years · ${d.available_from}-${d.available_to}</div>
      <div style="display:flex;justify-content:space-between;align-items:center">
        <div class="doctor-fee">$${d.consultation_fee}</div>
        <button class="btn btn-sm btn-primary" onclick="quickBook(${d.id})">Book</button>
      </div>
    </div>
  `).join('');
}

async function filterDoctors() {
  const deptId = document.getElementById('dept-filter').value;
  const url = deptId ? `/api/doctors/?department_id=${deptId}` : '/api/doctors/';
  const doctors = await apiCall(url);
  renderDoctors(doctors || []);
}

async function showBookingModal() {
  document.getElementById('booking-modal').style.display = 'flex';
  const doctors = await apiCall('/api/doctors/');
  const sel = document.getElementById('book-doctor');
  sel.innerHTML = doctors.map(d => `<option value="${d.id}">Dr. ${d.user?.full_name} - ${d.specialization}</option>`).join('');
  const now = new Date();
  now.setHours(now.getHours() + 1);
  document.getElementById('book-date').value = now.toISOString().slice(0, 16);
}

function quickBook(doctorId) {
  document.querySelectorAll('main section').forEach(s => s.style.display = 'none');
  document.getElementById('section-appointments').style.display = 'block';
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  const activeBtn = document.querySelector(`.nav-btn[onclick*="'appointments'"]`);
  if (activeBtn) activeBtn.classList.add('active');
  showBookingModal().then(() => {
    document.getElementById('book-doctor').value = doctorId;
  });
}

function closeModal() {
  document.getElementById('booking-modal').style.display = 'none';
}

async function bookAppointment() {
  const rawDate = document.getElementById('book-date').value;
  const body = {
    doctor_id: parseInt(document.getElementById('book-doctor').value),
    appointment_date: rawDate.length === 16 ? rawDate + ':00' : rawDate,  // ensure seconds
    reason: document.getElementById('book-reason').value
  };
  const res = await fetch('/api/appointments/', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  const data = await res.json();
  if (res.ok) {
    closeModal();
    loadAppointments();
    alert('✅ Appointment booked successfully!');
  } else {
    alert('❌ ' + (data.detail || 'Booking failed'));
  }
}

async function cancelAppt(id) {
  if (!confirm('Cancel this appointment?')) return;
  await fetch(`/api/appointments/${id}`, {
    method: 'DELETE', headers: { 'Authorization': `Bearer ${token}` }
  });
  loadAppointments();
}

async function loadPrescriptions() {
  const data = await apiCall('/api/prescriptions/');
  const container = document.getElementById('records-content');
  if (!data || data.length === 0) {
    container.innerHTML = `<div class="empty-state"><div class="empty-icon">💊</div><p>No prescriptions found.</p></div>`;
    return;
  }
  container.innerHTML = data.map(rx => `
    <div class="card">
      <div class="card-title">Prescription #${rx.id}</div>
      <div class="card-meta">📋 Diagnosis: ${rx.diagnosis || 'N/A'}</div>
      <div class="card-meta">🗓️ ${new Date(rx.created_at).toLocaleDateString()}</div>
      ${rx.medicines?.length ? `<div style="margin-top:0.75rem"><strong>Medicines:</strong><ul style="margin-top:0.5rem;padding-left:1.25rem">
        ${rx.medicines.map(m => `<li style="font-size:0.875rem">${m.name} — ${m.dosage}, ${m.frequency} for ${m.duration}</li>`).join('')}
      </ul></div>` : ''}
      ${rx.instructions ? `<div style="margin-top:0.5rem;font-size:0.875rem;color:#64748b">📝 ${rx.instructions}</div>` : ''}
    </div>
  `).join('');
}

async function loadBills() {
  const data = await apiCall('/api/billing/');
  const container = document.getElementById('bills-list');
  if (!data || data.length === 0) {
    container.innerHTML = `<div class="empty-state"><div class="empty-icon">💳</div><p>No bills found.</p></div>`;
    return;
  }
  container.innerHTML = data.map(b => `
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:start">
        <div>
          <div class="card-title">Bill #${b.id}</div>
          <div class="card-meta">🗓️ ${new Date(b.created_at).toLocaleDateString()}</div>
        </div>
        <span class="badge badge-${b.payment_status}">${b.payment_status}</span>
      </div>
      <div style="margin-top:1rem;display:flex;justify-content:space-between">
        <span style="color:#64748b">Total Amount</span>
        <strong style="font-size:1.1rem">$${b.total.toFixed(2)}</strong>
      </div>
    </div>
  `).join('');
}