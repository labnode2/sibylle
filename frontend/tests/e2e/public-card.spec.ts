// US15: a press card made public from the profile, seen without an account by its link and in
// another site's iframe, then private again, and public once more at the same address.
import { expect, test } from '@playwright/test';

import { createNewsroom, newPerson, notes } from './helpers';

test('a public press card, by its link and in an iframe', async ({ browser }, testInfo) => {
  test.setTimeout(90_000);
  const ines = await newPerson(browser, testInfo, 'Inès');
  await createNewsroom(ines, 'Sophia Office', 'Inès');
  await ines.context().grantPermissions(['clipboard-read', 'clipboard-write']);

  // Private at first: the switch is off, and there is no link.
  await ines.getByRole('link', { name: 'PROFIL' }).click();
  const setting = ines.getByRole('region', { name: 'Profil public' });
  const toggle = setting.getByRole('switch', { name: 'Profil public' });
  await expect(toggle).toHaveAttribute('aria-checked', 'false');
  await expect(setting).toContainText('PRIVÉE · SEULS LES MEMBRES DE SOPHIA OFFICE LA VOIENT');
  await expect(setting.getByLabel('LIEN PUBLIC')).toHaveCount(0);

  // Public: its link, and the code of an iframe that shows it.
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-checked', 'true');
  await expect(notes(ines)).toContainText('Ta carte est publique');
  await expect(setting).toContainText('PUBLIQUE · TOUT LE MONDE LA VOIT AVEC LE LIEN');
  const link = setting.getByLabel('LIEN PUBLIC');
  await expect(link).toHaveValue(/\/carte\/[\w-]{16}$/);
  const url = await link.inputValue();
  const code = await setting.getByLabel("CODE D'INTÉGRATION (IFRAME)").inputValue();
  expect(code).toBe(
    `<iframe src="${url}" title="Carte de presse de Inès sur Sibylle" width="400" ` +
      `height="470" style="border:0;max-width:100%" loading="lazy"></iframe>`,
  );
  await setting.getByRole('button', { name: 'Copier le lien' }).click();
  await expect(notes(ines)).toContainText('Lien de ta carte copié.');
  expect(await ines.evaluate(() => navigator.clipboard.readText())).toBe(url);

  // Someone without an account: the card, its figures, and nothing of the app around it.
  const visitor = await (await browser.newContext({ ...testInfo.project.use })).newPage();
  await visitor.goto(url);
  const card = visitor.getByRole('region', { name: 'Carte de presse' });
  await expect(card.getByRole('heading', { name: 'Inès' })).toBeVisible();
  await expect(card).toContainText('RÉDACTION EN CHEF SOPHIA OFFICE');
  await expect(card).toContainText('CARTE DE PRESSE N° 0001');
  await expect(visitor.getByLabel('Statistiques')).toContainText('LAURIERS');
  await expect(visitor.getByRole('link', { name: 'PROFIL' })).toHaveCount(0);
  await expect(visitor).toHaveURL(url);

  // The same card in another site's iframe: a page of the API's 127.0.0.1, another site than
  // localhost, rewritten. A made-up site would not do: Chrome keeps a page that comes from no
  // address from framing the local network.
  await visitor.goto(`http://127.0.0.1:${process.env.SIBYLLE_API_PORT ?? '8001'}/api/health`);
  await visitor.setContent(`<h1>Mon blog</h1>${code}`);
  const framed = visitor.frameLocator('iframe[title="Carte de presse de Inès sur Sibylle"]');
  await expect(framed.getByRole('heading', { name: 'Inès', exact: true })).toBeVisible();

  // Private again: the link shows nothing more, the iframe neither.
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-checked', 'false');
  await expect(link).toHaveCount(0);
  await visitor.goto(url);
  await expect(visitor.getByRole('alert')).toHaveText(
    "Cette carte de presse n'est pas publique, ou n'existe plus.",
  );

  // Public once more, at the same address.
  await toggle.click();
  await expect(link).toHaveValue(url);
  await visitor.reload();
  await expect(visitor.getByRole('heading', { name: 'Inès', exact: true })).toBeVisible();
  await visitor.context().close();
});
