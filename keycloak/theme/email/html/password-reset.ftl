<#-- Changer de mot de passe: the app's own e-mail until specs/002-keycloak-auth, in its frame. -->
<#import "template.ftl" as layout>
<@layout.emailLayout title=msg("passwordResetSubject")>
<@layout.hello/>
<@layout.paragraph>${msg("sibylle.resetLead")}</@layout.paragraph>
<@layout.button url=link label=msg("sibylle.resetButton")/>
<@layout.note>${msg("sibylle.resetNote", linkExpirationFormatter(linkExpiration))}</@layout.note>
</@layout.emailLayout>
