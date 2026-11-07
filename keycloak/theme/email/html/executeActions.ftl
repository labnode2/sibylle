<#-- What the app asks of an account by e-mail (Keycloak's execute-actions-email): a password to
     choose, an address to confirm… -->
<#outputformat "plainText">
<#assign requiredActionsText><#if requiredActions??><#list requiredActions as reqActionItem>${msg("requiredAction.${reqActionItem}")}<#sep>, </#list></#if></#assign>
</#outputformat>
<#import "template.ftl" as layout>
<@layout.emailLayout title=msg("executeActionsSubject")>
<@layout.hello/>
<@layout.paragraph>${msg("sibylle.actionsLead", requiredActionsText)}</@layout.paragraph>
<@layout.button url=link label=msg("sibylle.actionsButton")/>
<@layout.note>${msg("sibylle.actionsNote", linkExpirationFormatter(linkExpiration))}</@layout.note>
</@layout.emailLayout>
