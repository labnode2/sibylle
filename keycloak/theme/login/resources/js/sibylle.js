// What Sibylle's sign-in pages do in the browser: the crystal ball of the masthead, the new
// password that Keycloak wants twice, and one submit per form. crystal-ball.js is a copy of
// crystal-ball-kit/src/crystal-ball.js (keycloak/check-theme.sh checks that it stays the same).
import { animate, variantFor } from './crystal-ball.js';

// The ball of the day, a season or a holiday, as in the app (frontend/src/ui/CrystalBall.tsx):
// played twice, then still, and never when the system asks for reduced motion; again on hover.
for (const canvas of document.querySelectorAll('canvas[data-crystal-ball]')) {
  const player = animate(canvas, variantFor(new Date()));
  canvas.addEventListener('mouseenter', () => player.play());
}

document.addEventListener('submit', (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement) || event.defaultPrevented) return;

  // A new password is typed once, as in the app; Keycloak compares it with the field named by
  // data-confirmed-by, sent here with the same value. Without JavaScript the page shows that
  // second field itself (field.ftl, newPassword).
  for (const input of form.querySelectorAll('input[data-confirmed-by]')) {
    let confirm = form.elements.namedItem(input.dataset.confirmedBy);
    if (!confirm) {
      confirm = document.createElement('input');
      confirm.type = 'hidden';
      confirm.name = input.dataset.confirmedBy;
      form.append(confirm);
    }
    confirm.value = input.value;
  }

  // One submit per form: the buttons go grey while the next page loads. Only once the form's
  // data is taken, or the button pressed (cancel-aia, for instance) would not be sent.
  const buttons = form.querySelectorAll('button[type="submit"], input[type="submit"]');
  setTimeout(() => {
    for (const button of buttons) button.disabled = true;
  });
});

// A link to another sign-in service is followed once (the base theme's data-once-link).
document.addEventListener('click', (event) => {
  const link = event.target instanceof Element && event.target.closest('a[data-once-link]');
  if (!link) return;
  if (link.getAttribute('aria-disabled') === 'true') {
    event.preventDefault();
    return;
  }
  link.setAttribute('role', 'link');
  link.setAttribute('aria-disabled', 'true');
});

// A page shown again from the browser's history keeps its buttons usable.
window.addEventListener('pageshow', (event) => {
  if (!event.persisted) return;
  for (const button of document.querySelectorAll('button[type="submit"], input[type="submit"]')) {
    button.disabled = false;
  }
});
