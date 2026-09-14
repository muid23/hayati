(function(){
  let sessionId = null;
  let patientId = localStorage.getItem('hayati_patient_id') || crypto.randomUUID();
  localStorage.setItem('hayati_patient_id', patientId);

  const $ = id => document.getElementById(id);
  const chat = $('chat'), welcome = $('welcomeState'), form = $('inputForm'), input = $('messageInput'), sendBtn = $('sendBtn');

  function timeNow(){return new Intl.DateTimeFormat([], {hour:'numeric',minute:'2-digit'}).format(new Date());}
  function scrollBottom(){chat.scrollTop=chat.scrollHeight;}
  function hideWelcome(){if(welcome) welcome.style.display='none';}
  function addMessage(sender,text){
    hideWelcome();
    const row=document.createElement('div'); row.className='msg-row '+sender;
    const avatar=document.createElement('div'); avatar.className='msg-avatar '+(sender==='user'?'user-avatar':'');
    avatar.innerHTML=sender==='user'?'<i class="fa-solid fa-user"></i>':'<i class="fa-solid fa-heart-pulse"></i>';
    const col=document.createElement('div'); col.className='bubble-col';
    const bubble=document.createElement('div'); bubble.className='bubble'; bubble.textContent=text; col.appendChild(bubble);
    const tm=document.createElement('div'); tm.className='msg-time'; tm.textContent=timeNow(); col.appendChild(tm);
    row.appendChild(avatar); row.appendChild(col); chat.appendChild(row); scrollBottom();
  }
  function showTyping(){
    const row=document.createElement('div'); row.id='typingRow'; row.className='msg-row bot';
    row.innerHTML='<div class="msg-avatar"><i class="fa-solid fa-heart-pulse"></i></div><div class="typing-bubble"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></div>';
    chat.appendChild(row); scrollBottom();
  }
  function hideTyping(){const el=$('typingRow');if(el)el.remove();}
  function autosize(){input.style.height='auto';input.style.height=Math.min(input.scrollHeight,110)+'px';}
  function updateSend(){sendBtn.disabled=!input.value.trim();}

  async function loadMemory(){
    try{
      const r=await fetch(`/api/v1/patients/${encodeURIComponent(patientId)}`); if(!r.ok) throw Error();
      const m=await r.json(); renderMemory(m);
    }catch(e){console.warn('Memory load failed',e)}
  }
  function renderMemory(m){
    const p=m.patient||{};
    $('memoryName').textContent=p.name||'Guest Patient';
    const bits=[]; if(p.age!==null&&p.age!==undefined)bits.push(p.age+' yrs'); if(p.sex)bits.push(p.sex); if(p.location)bits.push(p.location);
    $('memoryMeta').textContent=bits.join(' · ')||'No personal details added';
    const symptoms=m.symptoms||[]; $('symptomCount').textContent=symptoms.length; if($('memoryConsultations'))$('memoryConsultations').textContent=m.consultation_count||0; if($('memorySymptoms'))$('memorySymptoms').textContent=symptoms.length; if($('memoryDetails'))$('memoryDetails').textContent=[p.age,p.sex,p.location,(p.conditions||[]).length,(p.allergies||[]).length,(p.medications||[]).length,p.notes].filter(v=>v!==null&&v!==undefined&&v!==''&&!(Array.isArray(v)&&v.length===0)).length;
    $('symptomList').innerHTML=symptoms.length?symptoms.slice(0,12).map(s=>`<span class="symptom-tag">${escapeHtml(s.symptom)}</span>`).join(''):'<div class="empty-mini">Symptoms mentioned in your conversations will appear here.</div>';
    $('fullSymptomList').innerHTML=symptoms.length?symptoms.map(s=>`<div class="symptom-row"><div><strong>${escapeHtml(s.symptom)}</strong>${s.duration_text?`<small>Reported for ${escapeHtml(s.duration_text)}</small>`:''}</div><span>${s.mentions} mention${s.mentions===1?'':'s'} · ${formatDate(s.last_seen)}</span></div>`).join(''):'<div class="empty-mini">No symptoms have been remembered yet. Start a consultation and describe how you feel.</div>';
    fillPatientForm(p);
  }
  function escapeHtml(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  function formatDate(s){try{return new Intl.DateTimeFormat([], {month:'short',day:'numeric'}).format(new Date(s))}catch{return ''}}
  function csvValue(id){return ($(id).value||'').split(',').map(x=>x.trim()).filter(Boolean)}
  function fillPatientForm(p){$('patientName').value=p.name||'Guest Patient';$('patientAge').value=p.age??'';$('patientSex').value=p.sex||'';$('patientLocation').value=p.location||'';$('patientConditions').value=(p.conditions||[]).join(', ');$('patientAllergies').value=(p.allergies||[]).join(', ');$('patientMedications').value=(p.medications||[]).join(', ');$('patientNotes').value=p.notes||'';}
  async function savePatient(){
    const body={name:$('patientName').value.trim()||'Guest Patient',age:$('patientAge').value?Number($('patientAge').value):null,sex:$('patientSex').value||null,location:$('patientLocation').value.trim()||null,conditions:csvValue('patientConditions'),allergies:csvValue('patientAllergies'),medications:csvValue('patientMedications'),notes:$('patientNotes').value};
    const r=await fetch(`/api/v1/patients/${encodeURIComponent(patientId)}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); if(!r.ok)throw Error('Could not save patient'); await loadMemory(); showView('chat');
  }

  async function botRespond(text){
    showTyping();
    try{
      const r=await fetch('/api/v1/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text,session_id:sessionId,patient_id:patientId})});
      if(!r.ok)throw Error(`HTTP ${r.status}`); const res=await r.json(); sessionId=res.session_id; patientId=res.patient_id; localStorage.setItem('hayati_patient_id',patientId);
      addMessage('bot',res.reply); await loadMemory();
      if(res.assessment?.results?.length){const top=res.assessment.results.slice(0,3).map(x=>`${x.condition} — ${x.score}% symptom-pattern match`).join('\n');addMessage('bot','Educational pattern check — not a diagnosis:\n'+top);}
    }catch(e){addMessage('bot','I’m having trouble connecting to Hayati right now. Please try again in a moment.');console.error(e)}finally{hideTyping()}
  }
  function sendMessage(value){const text=(typeof value==='string'?value:input.value).trim();if(!text)return;addMessage('user',text);input.value='';autosize();updateSend();botRespond(text)}

  function showView(name){
    document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));$(name+'View').classList.add('active');
    document.querySelectorAll('.nav-item').forEach(n=>n.classList.toggle('active',n.dataset.view===name));
    $('viewTitle').textContent=name==='chat'?'Consultation':name==='memory'?'Patient memory':'Surveillance overview';
    if(name==='memory')loadMemory(); if(name==='surveillance')loadRisk();
  }
  document.querySelectorAll('.nav-item').forEach(n=>n.addEventListener('click',()=>{showView(n.dataset.view);$('sidebar').classList.remove('open')}));
  $('menuBtn').addEventListener('click',()=>$('sidebar').classList.toggle('open'));
  $('profileBtn').addEventListener('click',()=>showView('memory'));$('openMemoryBtn').addEventListener('click',()=>showView('memory'));$('editMemoryBtn').addEventListener('click',()=>showView('memory'));
  $('savePatientTop').addEventListener('click',()=>savePatient().catch(()=>alert('Hayati could not save the patient record. Please try again.')));
  $('newChatBtn').addEventListener('click',()=>{document.querySelectorAll('.msg-row').forEach(x=>x.remove());sessionId=null;if(welcome)welcome.style.display='';input.value='';autosize();updateSend();showView('chat')});
  form.addEventListener('submit',e=>{e.preventDefault();sendMessage()});input.addEventListener('input',()=>{autosize();updateSend()});
  document.querySelectorAll('.starter-chip').forEach(c=>c.addEventListener('click',()=>sendMessage(c.dataset.msg)));
  $('refreshRisk').addEventListener('click',loadRisk);
  async function loadRisk(){try{const r=await fetch('/api/v1/surveillance/risk');const x=await r.json();$('riskLevel').textContent=(x.risk_level||'—').toUpperCase();$('riskText').textContent=x.interpretation||'No analysis yet';$('recentReports').textContent=x.recent_reports??0;$('growthReports').textContent=(x.growth_percent??0)+'%';$('severeReports').textContent=(x.severe_report_percent??0)+'%'}catch(e){$('riskText').textContent='Unable to load surveillance signal.'}}
  window.addEventListener('load',()=>{loadMemory();setTimeout(()=>{document.body.classList.add('ready')},300)});autosize();updateSend();
})();
