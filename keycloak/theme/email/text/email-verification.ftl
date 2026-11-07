<#ftl output_format="plainText">
<#-- Confirme ton adresse (backend/src/sibylle/notify/templates/fr/verify_email.txt). -->
<#if (user.firstName)?has_content>${msg("sibylle.hello", user.firstName)}<#else>${msg("sibylle.helloNoName")}</#if>

${msg("sibylle.verifyLead")}

${link}

${msg("sibylle.verifyNote", linkExpirationFormatter(linkExpiration))}

${msg("sibylle.signature")}
