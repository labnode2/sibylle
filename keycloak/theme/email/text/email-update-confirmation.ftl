<#ftl output_format="plainText">
<#-- A new address to confirm, sent to that address. -->
<#if (user.firstName)?has_content>${msg("sibylle.hello", user.firstName)}<#else>${msg("sibylle.helloNoName")}</#if>

${msg("sibylle.updateEmailLead", newEmail)}

${link}

${msg("sibylle.updateEmailNote", linkExpirationFormatter(linkExpiration))}

${msg("sibylle.signature")}
