<#-- Confirme ton adresse: the app's own e-mail until specs/002-keycloak-auth, in its frame. -->
<#import "template.ftl" as layout>
<@layout.emailLayout title=msg("emailVerificationSubject")>
<@layout.hello/>
<@layout.paragraph>${msg("sibylle.verifyLead")}</@layout.paragraph>
<@layout.button url=link label=msg("sibylle.verifyButton")/>
<@layout.note>${msg("sibylle.verifyNote", linkExpirationFormatter(linkExpiration))}</@layout.note>
</@layout.emailLayout>
