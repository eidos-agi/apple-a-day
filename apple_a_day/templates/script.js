// Level pills
function setLevel(n) {
  document.querySelectorAll('.level-pill').forEach((p, i) => p.classList.toggle('active', i === n - 1));
  document.querySelectorAll('.l2').forEach(s => s.classList.toggle('visible', n >= 2));
  document.querySelectorAll('.l3').forEach(s => s.classList.toggle('visible', n >= 3));
  // Show/hide sidebar nav links to match
  document.querySelectorAll('.sidebar .nav-l2').forEach(el => el.classList.toggle('nav-show', n >= 2));
  document.querySelectorAll('.sidebar .nav-l3').forEach(el => el.classList.toggle('nav-show', n >= 3));
  window._currentLevel = n;
}
window._currentLevel = 1;

// Sidebar nav clicks — highlight immediately + auto-expand level
document.querySelectorAll('.sidebar nav a').forEach(a => {
  a.addEventListener('click', (e) => {
    const id = a.getAttribute('href')?.slice(1);
    const el = id && document.getElementById(id);
    if (!el) return;

    // Immediately highlight this link as active
    navLinks.forEach(l => l.classList.remove('active'));
    a.classList.add('active');
    window._clickedNav = true;

    // Auto-expand level if target is hidden
    const inL3 = el.closest('.l3');
    const inL2 = el.closest('.l2');
    if (inL3 && window._currentLevel < 3) {
      setLevel(3);
    } else if (inL2 && window._currentLevel < 2) {
      setLevel(2);
    }

    // Scroll after a tick so the DOM has expanded
    e.preventDefault();
    setTimeout(() => {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      // Re-enable scroll-based highlighting after animation
      setTimeout(() => { window._clickedNav = false; }, 500);
    }, 50);
  });
});

// Apple scroll progress + active nav highlighting
const dot = document.getElementById('appleDot');
const navLinks = document.querySelectorAll('.sidebar nav a');
window.addEventListener('scroll', () => {
  const maxScroll = document.body.scrollHeight - window.innerHeight;
  const pct = maxScroll > 0 ? (window.scrollY / maxScroll * 100) : 0;
  if (dot) dot.style.left = Math.min(pct, 95) + '%';

  // Highlight active nav link (skip if user just clicked — let click win)
  if (!window._clickedNav) {
    let active = null;
    navLinks.forEach(a => {
      const id = a.getAttribute('href')?.slice(1);
      const el = id && document.getElementById(id);
      if (el && el.getBoundingClientRect().top <= 80) active = a;
    });
    navLinks.forEach(a => a.classList.remove('active'));
    if (active) active.classList.add('active');
  }
});
