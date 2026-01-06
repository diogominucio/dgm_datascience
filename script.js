// ===========================
// Mobile Menu Toggle
// ===========================
const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
const navLinks = document.querySelector('.nav-links');

if (mobileMenuBtn) {
    mobileMenuBtn.addEventListener('click', () => {
        navLinks.classList.toggle('active');
        mobileMenuBtn.classList.toggle('active');
    });
}

// ===========================
// Smooth Scroll
// ===========================
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            const navHeight = document.querySelector('.navbar').offsetHeight;
            const targetPosition = target.offsetTop - navHeight;

            window.scrollTo({
                top: targetPosition,
                behavior: 'smooth'
            });

            // Close mobile menu if open
            if (navLinks.classList.contains('active')) {
                navLinks.classList.remove('active');
                mobileMenuBtn.classList.remove('active');
            }
        }
    });
});

// ===========================
// Scroll to Contact Function
// ===========================
function scrollToContact() {
    const contactSection = document.getElementById('contact');
    const navHeight = document.querySelector('.navbar').offsetHeight;
    const targetPosition = contactSection.offsetTop - navHeight;

    window.scrollTo({
        top: targetPosition,
        behavior: 'smooth'
    });
}

// ===========================
// Navbar Scroll Effect
// ===========================
let lastScroll = 0;
const navbar = document.querySelector('.navbar');

window.addEventListener('scroll', () => {
    const currentScroll = window.pageYOffset;

    if (currentScroll > 100) {
        navbar.style.boxShadow = '0 2px 20px rgba(0, 0, 0, 0.1)';
    } else {
        navbar.style.boxShadow = 'none';
    }

    lastScroll = currentScroll;
});

// ===========================
// Form Handling
// ===========================
const leadForm = document.getElementById('leadForm');
const formSuccess = document.getElementById('formSuccess');

if (leadForm) {
    leadForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        // Get form data
        const formData = new FormData(leadForm);
        const data = Object.fromEntries(formData);

        // Show loading state
        const submitBtn = leadForm.querySelector('.btn-submit');
        const originalText = submitBtn.textContent;
        submitBtn.textContent = 'Submitting...';
        submitBtn.disabled = true;

        // Simulate API call (replace with actual API endpoint)
        try {
            // In production, replace this with actual API call
            // const response = await fetch('YOUR_API_ENDPOINT', {
            //     method: 'POST',
            //     headers: {
            //         'Content-Type': 'application/json',
            //     },
            //     body: JSON.stringify(data),
            // });

            // Simulate delay
            await new Promise(resolve => setTimeout(resolve, 1500));

            // Log to console (for development)
            console.log('Form submitted with data:', data);

            // Store in localStorage (temporary solution)
            const leads = JSON.parse(localStorage.getItem('leads') || '[]');
            leads.push({
                ...data,
                timestamp: new Date().toISOString()
            });
            localStorage.setItem('leads', JSON.stringify(leads));

            // Show success message
            leadForm.style.display = 'none';
            formSuccess.style.display = 'block';

            // Track conversion (Google Analytics example)
            if (typeof gtag !== 'undefined') {
                gtag('event', 'conversion', {
                    'send_to': 'AW-XXXXXXXXX/XXXXXXXXXXXXXX',
                    'value': 1.0,
                    'currency': 'USD'
                });
            }

            // Facebook Pixel (if installed)
            if (typeof fbq !== 'undefined') {
                fbq('track', 'Lead');
            }

        } catch (error) {
            console.error('Form submission error:', error);
            alert('An error occurred while submitting the form. Please try again.');
            submitBtn.textContent = originalText;
            submitBtn.disabled = false;
        }
    });
}

// ===========================
// Intersection Observer for Animations
// ===========================
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -100px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
        }
    });
}, observerOptions);

// Observe elements
document.querySelectorAll('.process-card, .service-card, .why-card, .insight-item').forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(30px)';
    el.style.transition = 'opacity 0.6s ease-out, transform 0.6s ease-out';
    observer.observe(el);
});

// ===========================
// Form Validation Enhancement
// ===========================
const formInputs = document.querySelectorAll('.form-group input, .form-group textarea, .form-group select');

formInputs.forEach(input => {
    input.addEventListener('blur', () => {
        if (input.hasAttribute('required') && !input.value.trim()) {
            input.style.borderColor = '#EF4444';
        } else {
            input.style.borderColor = '';
        }
    });

    input.addEventListener('input', () => {
        if (input.style.borderColor === 'rgb(239, 68, 68)') {
            input.style.borderColor = '';
        }
    });
});

// Email validation
const emailInput = document.getElementById('email');
if (emailInput) {
    emailInput.addEventListener('blur', () => {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (emailInput.value && !emailRegex.test(emailInput.value)) {
            emailInput.style.borderColor = '#EF4444';
        }
    });
}

// Phone formatting (US format)
const phoneInput = document.getElementById('phone');
if (phoneInput) {
    phoneInput.addEventListener('input', (e) => {
        let value = e.target.value.replace(/\D/g, '');

        if (value.length <= 10) {
            if (value.length >= 6) {
                value = value.replace(/(\d{3})(\d{3})(\d{0,4})/, '($1) $2-$3');
            } else if (value.length >= 3) {
                value = value.replace(/(\d{3})(\d{0,3})/, '($1) $2');
            }
            e.target.value = value;
        } else {
            e.target.value = value.slice(0, 10);
        }
    });
}

// ===========================
// Stats Counter Animation
// ===========================
function animateCounter(element, target, suffix = '') {
    let current = 0;
    const increment = target / 60;
    const timer = setInterval(() => {
        current += increment;
        if (current >= target) {
            element.textContent = target + suffix;
            clearInterval(timer);
        } else {
            element.textContent = Math.floor(current) + suffix;
        }
    }, 30);
}

// Observe stats section
const statsObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting && !entry.target.dataset.animated) {
            entry.target.dataset.animated = 'true';
            const stats = entry.target.querySelectorAll('.stat-number');

            stats.forEach(stat => {
                const text = stat.textContent;
                const number = parseInt(text.replace(/\D/g, ''));
                const suffix = text.replace(/[\d\s]/g, '');
                animateCounter(stat, number, suffix);
            });
        }
    });
}, { threshold: 0.5 });

const heroStats = document.querySelector('.hero-stats');
if (heroStats) {
    statsObserver.observe(heroStats);
}

// ===========================
// Dynamic Year in Footer
// ===========================
const currentYear = new Date().getFullYear();
const yearElements = document.querySelectorAll('.footer-bottom p');
yearElements.forEach(el => {
    if (el.textContent.includes('2026')) {
        el.textContent = el.textContent.replace('2026', currentYear);
    }
});

// ===========================
// Prevent Form Resubmission
// ===========================
if (performance.navigation.type === performance.navigation.TYPE_RELOAD) {
    if (formSuccess && formSuccess.style.display === 'block') {
        formSuccess.style.display = 'none';
        leadForm.style.display = 'flex';
        leadForm.reset();
    }
}

// ===========================
// Console Welcome Message
// ===========================
console.log('%c👋 Olá, Developer!', 'font-size: 20px; font-weight: bold; color: #E97451;');
console.log('%cInteressado em trabalhar conosco?', 'font-size: 14px; color: #4A4A4A;');
console.log('%cEnvie um email para: diogominucio@mubbgroup.com', 'font-size: 14px; color: #4A4A4A;');

// ===========================
// Export leads function (for testing)
// ===========================
window.getLeads = function() {
    const leads = JSON.parse(localStorage.getItem('leads') || '[]');
    console.table(leads);
    return leads;
};

window.clearLeads = function() {
    localStorage.removeItem('leads');
    console.log('Leads cleared from localStorage');
};

console.log('%cDeveloper Tools:', 'font-size: 14px; font-weight: bold; color: #E97451;');
console.log('%cgetLeads() - View all submitted leads', 'font-size: 12px; color: #6B6B6B;');
console.log('%cclearLeads() - Clear all leads from storage', 'font-size: 12px; color: #6B6B6B;');
