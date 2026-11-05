(() => {
  const analyze = document.querySelector('#analyze');
  const apply = document.querySelector('#apply-plan');
  const message = document.querySelector('#analysis-status');
  const result = document.querySelector('#analysis-result');
  const imageInput = document.querySelector('#image');
  const notes = document.querySelector('#design-notes');
  let plan = null;
  let configured = false;
  let busy = false;
  let version = 0;

  function invalidate() {
    version++;
    plan = null;
    result.replaceChildren();
    apply.disabled = true;
    message.textContent = configured ? 'Sẵn sàng phân tích ảnh bằng OpenAI.' : 'Máy chủ chưa cấu hình OpenAI.';
  }
  for (const id of ['image', 'width', 'design-notes']) {
    document.getElementById(id).addEventListener('input', invalidate);
  }
  fetch('/api/config').then(response => {
    if (!response.ok) throw Error('Không đọc được cấu hình phân tích.');
    return response.json();
  }).then(data => {
    configured = data.analysis.configured;
    analyze.disabled = !configured;
    invalidate();
  }).catch(error => { message.textContent = error.message; });

  analyze.addEventListener('click', async () => {
    if (busy) return;
    const image = imageInput.files[0];
    const width = document.querySelector('#width');
    if (!image) { message.textContent = 'Chọn ảnh trước khi phân tích.'; return; }
    if (!width.reportValidity() || !notes.reportValidity()) return;
    if (image.size > 10000000) { message.textContent = 'Ảnh tối đa 10 MB.'; return; }
    busy = true;
    analyze.disabled = true;
    apply.disabled = true;
    plan = null;
    result.replaceChildren();
    const submittedVersion = version;
    message.textContent = 'Đang gửi ảnh tới OpenAI để đề xuất phương án thêu…';
    try {
      const data = new FormData();
      data.set('image', image);
      data.set('width_mm', width.value);
      data.set('notes', notes.value);
      const response = await fetch('/api/analyze', { method: 'POST', body: data });
      const body = await response.json();
      if (submittedVersion !== version) {
        message.textContent = 'Ảnh hoặc yêu cầu đã đổi. Hãy phân tích lại để dùng kết quả đúng.';
        return;
      }
      if (!response.ok) throw Error(typeof body.detail === 'string' ? body.detail : 'Yêu cầu phân tích không hợp lệ.');
      plan = body.plan;
      const summary = document.createElement('p');
      summary.textContent = plan.summary;
      const settings = document.createElement('p');
      settings.textContent = `${plan.colors} màu · satin ${plan.satin_spacing} mm · tatami ${plan.tatami_spacing} mm / mũi ${plan.tatami_length} mm · góc ${plan.tatami_angle}°`;
      result.append(summary, settings);
      const list = document.createElement('ul');
      for (const region of plan.regions) {
        const li = document.createElement('li');
        li.textContent = `${region.name} — ${region.stitch_type}: ${region.reason}`;
        list.append(li);
      }
      result.append(list);
      for (const caution of plan.cautions) {
        const p = document.createElement('p');
        p.className = 'settings-note';
        p.textContent = caution;
        result.append(p);
      }
      message.textContent = 'Đã có đề xuất. Bạn xem lại trước khi áp dụng; các vùng là gợi ý, chưa tự chia cột satin.';
      apply.disabled = false;
    } catch (error) {
      message.textContent = error.message;
    } finally {
      busy = false;
      analyze.disabled = !configured;
    }
  });

  apply.addEventListener('click', () => {
    if (!plan || busy) return;
    const settings = { colors: plan.colors, background: plan.background_mode,
      'satin-spacing': plan.satin_spacing, spacing: plan.tatami_spacing,
      'stitch-length': plan.tatami_length, angle: plan.tatami_angle };
    for (const [id, value] of Object.entries(settings)) {
      const field = document.getElementById(id);
      field.value = String(value);
      field.dispatchEvent(new Event('input', { bubbles: true }));
      field.dispatchEvent(new Event('change', { bubbles: true }));
    }
    message.textContent = 'Đã áp dụng thông số chung. Kiểm tra từng vùng và nhấn Tạo đường thêu để tạo tệp mới.';
  });
})();
