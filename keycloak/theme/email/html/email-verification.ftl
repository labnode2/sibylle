<#-- Confirme ton adresse (backend/src/sibylle/notify/templates/fr/verify_email.html). -->
<#import "template.ftl" as layout>
<@layout.emailLayout title=msg("emailVerificationSubject")>
<@layout.hello/>
<@layout.paragraph>${msg("sibylle.verifyLead")}</@layout.paragraph>
<@layout.button url=link label=msg("sibylle.verifyButton")/>
<@layout.note>${msg("sibylle.verifyNote", linkExpirationFormatter(linkExpiration))}</@layout.note>
</@layout.emailLayout>
