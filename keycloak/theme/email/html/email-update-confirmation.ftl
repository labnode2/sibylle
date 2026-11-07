<#-- A new address to confirm, sent to that address. -->
<#import "template.ftl" as layout>
<@layout.emailLayout title=msg("emailUpdateConfirmationSubject")>
<@layout.hello/>
<@layout.paragraph>${msg("sibylle.updateEmailLead", newEmail)}</@layout.paragraph>
<@layout.button url=link label=msg("sibylle.updateEmailButton")/>
<@layout.note>${msg("sibylle.updateEmailNote", linkExpirationFormatter(linkExpiration))}</@layout.note>
</@layout.emailLayout>
