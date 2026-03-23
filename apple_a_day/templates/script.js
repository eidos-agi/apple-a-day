// Level pills
function setLevel(n) {
  document.querySelectorAll('.level-pill').forEach((p, i) => p.classList.toggle('active', i === n - 1));
  document.querySelectorAll('.l2').forEach(s => s.style.display = n >= 2 ? 'block' : 'none');
  document.querySelectorAll('.l3').forEach(s => s.style.display = n >= 3 ? 'block' : 'none');
}

// Apple scroll progress + active nav highlighting
const dot = document.getElementById('appleDot');
const navLinks = document.querySelectorAll('.sidebar nav a');
window.addEventListener('scroll', () => {
  const pct = window.scrollY / (document.body.scrollHeight - window.innerHeight) * 100;
  if (dot) dot.style.left = Math.min(pct, 95) + '%';
  let active = null;
  navLinks.forEach(a => {
    const id = a.getAttribute('href')?.slice(1);
    const el = id && document.getElementById(id);
    if (el && el.getBoundingClientRect().top <= 80) active = a;
  });
  navLinks.forEach(a => a.classList.remove('active'));
  if (active) active.classList.add('active');
});
