<#ftl output_format="plainText">
<#-- Changer de mot de passe: the app's own e-mail until specs/002-keycloak-auth. -->
<#if (user.firstName)?has_content>${msg("sibylle.hello", user.firstName)}<#else>${msg("sibylle.helloNoName")}</#if>

${msg("sibylle.resetLead")}

${link}

${msg("sibylle.resetNote", linkExpirationFormatter(linkExpiration))}

${msg("sibylle.signature")}
