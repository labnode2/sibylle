<#-- Complete the account, when Keycloak lacks a field of the profile (an account brought from
     elsewhere, a field added to the realm): the fields in the sign-up's order. -->
<#import "template.ftl" as layout>
<#import "field.ftl" as field>
<@layout.registrationLayout displayMessage=messagesPerField.exists('global'); section>
    <#if section = "header">
        ${msg("loginProfileTitle")}
    <#elseif section = "form">
        <form id="kc-update-profile-form" class="form" action="${url.loginAction}" method="post" novalidate>
            <@field.profileFields/>
            <#if isAppInitiatedAction??>
                <div class="actions">
                    <button type="submit" class="button">${msg("doSubmit")}</button>
                    <button type="submit" name="cancel-aia" value="true" class="button button-secondary" formnovalidate>${msg("doCancel")}</button>
                </div>
            <#else>
                <button type="submit" class="button button-block">${msg("doSubmit")}</button>
            </#if>
        </form>
    </#if>
</@layout.registrationLayout>
