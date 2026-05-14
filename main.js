/* ============================================
   Language toggle
   ============================================ */
const langToggle = document.getElementById('langToggle');
let currentLang = 'ja';

function setLang(lang) {
  currentLang = lang;
  document.documentElement.lang = lang;
  document.querySelectorAll('[data-ja]').forEach(el => {
    el.classList.toggle('hidden', lang !== 'ja');
  });
  document.querySelectorAll('[data-en]').forEach(el => {
    el.classList.toggle('hidden', lang !== 'en');
  });
}

langToggle.addEventListener('click', () => {
  setLang(currentLang === 'ja' ? 'en' : 'ja');
});

/* ============================================
   Hamburger menu
   ============================================ */
const hamburger = document.getElementById('hamburger');
const mobileNav = document.getElementById('mobileNav');

hamburger.addEventListener('click', () => {
  mobileNav.classList.toggle('open');
});

mobileNav.querySelectorAll('a').forEach(link => {
  link.addEventListener('click', () => mobileNav.classList.remove('open'));
});

/* ============================================
   Publications tabs
   ============================================ */
const tabBtns  = document.querySelectorAll('.pub-tab-btn');
const panels   = document.querySelectorAll('.pub-panel');

tabBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    tabBtns.forEach(b => b.classList.remove('active'));
    panels.forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('panel-' + btn.dataset.tab).classList.add('active');
  });
});
