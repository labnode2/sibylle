<#-- The frame of Sibylle's e-mails, the same as the app's own
     (backend/src/sibylle/notify/templates/fr/base.html): « LA GAZETTE DE Sibylle », the double
     rule, the message, then the footer. Tables and inline styles, for mail clients. -->
<#macro emailLayout title="">
<!doctype html>
<html lang="${locale.language}" dir="${(ltr)?then('ltr','rtl')}">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title><#if title?has_content>${title}<#else>${msg("sibylle.name")}</#if></title>
  </head>
  <body style="margin:0;padding:0;background:#f3f4fa;color:#15162d;font-family:'Helvetica Neue',Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4fa;">
      <tr>
        <td align="center" style="padding:24px 16px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;">
            <tr>
              <td style="text-align:center;padding-bottom:12px;">
                <div style="font:600 11px/1 'Courier New',monospace;letter-spacing:0.24em;color:#4a4d6a;">${msg("sibylle.kicker")}</div>
                <div style="font:400 44px/1 Georgia,'Times New Roman',serif;color:#15162d;">${msg("sibylle.name")}</div>
              </td>
            </tr>
            <tr>
              <td style="border-top:4px solid #15162d;border-bottom:1px solid #15162d;height:2px;line-height:2px;font-size:0;">&nbsp;</td>
            </tr>
            <tr>
              <td style="padding:20px 0;font-size:16px;line-height:1.5;">
                <#nested>
              </td>
            </tr>
            <tr>
              <td style="border-top:1px solid #c9cbe4;padding-top:12px;font:500 11px/1.5 'Courier New',monospace;color:#4a4d6a;">
                ${msg("sibylle.footer")}
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
</#macro>

<#-- « Bonjour Camille, », or « Bonjour, » for an account without a first name. -->
<#macro hello>
<p style="margin:0 0 12px;"><#if (user.firstName)?has_content>${msg("sibylle.hello", user.firstName)}<#else>${msg("sibylle.helloNoName")}</#if></p>
</#macro>

<#macro paragraph>
<p style="margin:0 0 12px;"><#nested></p>
</#macro>

<#-- The link as the Gazette's ink button, then written out
     (backend/src/sibylle/notify/templates/fr/_button.html). -->
<#macro button url label>
<p style="margin:24px 0;">
  <a href="${url}" style="display:inline-block;background:#15162d;color:#ffffff;text-decoration:none;font-weight:700;padding:14px 20px;">${label}</a>
</p>
<p style="font:500 12px/1.5 'Courier New',monospace;color:#4a4d6a;word-break:break-all;">${url}</p>
</#macro>

<#-- The last word: how long the link lasts, what to do if nothing was asked. -->
<#macro note>
<p style="margin:0;color:#4a4d6a;font-size:14px;"><#nested></p>
</#macro>
