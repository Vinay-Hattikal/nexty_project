// Mobile Menu Toggle
const menuToggle = document.getElementById('menu-toggle');
const mobileMenu = document.getElementById('mobile-menu');
const menuIcon = document.getElementById('menu-icon');
const closeIcon = document.getElementById('close-icon');

if (menuToggle && mobileMenu) {
  menuToggle.addEventListener('click', () => {
    const isOpen = mobileMenu.classList.toggle('is-open');
    menuToggle.setAttribute('aria-expanded', isOpen);
    if (menuIcon && closeIcon) {
      menuIcon.style.display = isOpen ? 'none' : 'block';
      closeIcon.style.display = isOpen ? 'block' : 'none';
    }
  });
}

// Intersection Observer: reveal elements on scroll
const observer = new IntersectionObserver((entries, obs) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      const delay = parseInt(entry.target.getAttribute('data-delay')) || 0;
      setTimeout(() => entry.target.classList.add('is-visible'), delay);
      obs.unobserve(entry.target);
    }
  });
}, { rootMargin: '0px', threshold: 0.1 });

document.querySelectorAll('.initial-hidden').forEach(el => observer.observe(el));

// Testimonial Carousel
(function () {
  const track = document.getElementById('carousel-track');
  if (!track) return;
  const prevBtn = document.getElementById('prev-btn');
  const nextBtn = document.getElementById('next-btn');
  const dotsNav = document.getElementById('dots-nav');
  const announcer = document.getElementById('testimonial-announcer');
  const cards = Array.from(track.children);
  const cardCount = cards.length;
  let currentIndex = 0;
  let autoRotateInterval;

  const updateCarousel = (index) => {
    const offset = -index * 100;
    track.style.transform = `translateX(${offset}%)`;
    if (announcer) announcer.textContent = cards[index].getAttribute('aria-label') + ' displayed.';
    Array.from(dotsNav.children).forEach((dot, i) => {
      dot.classList.toggle('active', i === index);
      dot.setAttribute('aria-selected', i === index);
    });
    currentIndex = index;
  };

  const generateDots = () => {
    cards.forEach((_, i) => {
      const dot = document.createElement('button');
      dot.className = 'dot';
      dot.setAttribute('role', 'tab');
      dot.setAttribute('aria-controls', 'carousel-track');
      dot.setAttribute('aria-label', `Go to slide ${i + 1}`);
      dot.addEventListener('click', () => {
        stopAutoRotate();
        updateCarousel(i);
        startAutoRotate();
      });
      dotsNav.appendChild(dot);
    });
    updateCarousel(0);
  };

  const nextSlide = () => updateCarousel((currentIndex + 1) % cardCount);
  const prevSlide = () => updateCarousel((currentIndex - 1 + cardCount) % cardCount);

  const startAutoRotate = () => { autoRotateInterval = setInterval(nextSlide, 5500); };
  const stopAutoRotate = () => { clearInterval(autoRotateInterval); };

  if (nextBtn) nextBtn.addEventListener('click', () => { stopAutoRotate(); nextSlide(); startAutoRotate(); });
  if (prevBtn) prevBtn.addEventListener('click', () => { stopAutoRotate(); prevSlide(); startAutoRotate(); });

  track.addEventListener('mouseenter', stopAutoRotate);
  track.addEventListener('mouseleave', startAutoRotate);
  track.addEventListener('focusin', stopAutoRotate);
  track.addEventListener('focusout', startAutoRotate);

  cards.forEach(card => { card.addEventListener('mouseenter', stopAutoRotate); card.addEventListener('mouseleave', startAutoRotate); });

  generateDots();
  startAutoRotate();
})();
