// What Sibylle's sign-in pages do in the browser: the crystal ball of the masthead, the eye of
// the passwords, the new password that Keycloak wants twice, and one submit per form. crystal-ball.js is a copy of
// crystal-ball-kit/src/crystal-ball.js (keycloak/check-theme.sh checks that it stays the same).
import { animate, variantFor } from './crystal-ball.js';

// The ball of the day, a season or a holiday, as in the app (frontend/src/ui/CrystalBall.tsx):
// played twice, then still, and never when the system asks for reduced motion; again on hover.
for (const canvas of document.querySelectorAll('canvas[data-crystal-ball]')) {
  const player = animate(canvas, variantFor(new Date()));
  canvas.addEventListener('mouseenter', () => player.play());
}

// The eye beside each password (field.ftl, passwordToggle), shown only here: without JavaScript
// the field stays a plain password. It shows what is typed, or hides it again; a click leaves
// the focus and the cursor in the field.
for (const toggle of document.querySelectorAll('button[data-password-shows]')) {
  const input = document.getElementById(toggle.dataset.passwordShows);
  if (!(input instanceof HTMLInputElement)) continue;
  toggle.hidden = false;
  // The mouse does not take the focus from the field; the keyboard keeps it on the eye.
  toggle.addEventListener('mousedown', (event) => {
    if (document.activeElement === input) event.preventDefault();
  });
  toggle.addEventListener('click', () => {
    const shown = input.type === 'password';
    const typing = document.activeElement === input;
    const { selectionStart, selectionEnd, selectionDirection } = input;
    showPassword(toggle, input, shown);
    if (typing) {
      input.focus();
      input.setSelectionRange(selectionStart, selectionEnd, selectionDirection ?? undefined);
    }
  });
}

function showPassword(toggle, input, shown) {
  input.type = shown ? 'text' : 'password';
  toggle.setAttribute('aria-pressed', String(shown));
  toggle.setAttribute('aria-label', shown ? toggle.dataset.labelHide : toggle.dataset.labelShow);
}

document.addEventListener('submit', (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement) || event.defaultPrevented) return;

  // A password shown is sent as a password, so that the browser offers to keep it.
  for (const toggle of form.querySelectorAll('button[data-password-shows]')) {
    const input = document.getElementById(toggle.dataset.passwordShows);
    if (input instanceof HTMLInputElement) showPassword(toggle, input, false);
  }

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
