<#ftl output_format="plainText">
<#-- Changer de mot de passe (backend/src/sibylle/notify/templates/fr/reset_password.txt). -->
<#if (user.firstName)?has_content>${msg("sibylle.hello", user.firstName)}<#else>${msg("sibylle.helloNoName")}</#if>

${msg("sibylle.resetLead")}

${link}

${msg("sibylle.resetNote", linkExpirationFormatter(linkExpiration))}

${msg("sibylle.signature")}
