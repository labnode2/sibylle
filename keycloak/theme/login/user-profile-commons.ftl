<#-- The realm's user profile as the app's fields (field.ftl), for the base theme's pages that list
     it all in its own order (a new e-mail address, an account from another service…). Same macro
     and callbacks as the base theme's user-profile-commons.ftl. -->
<#import "field.ftl" as field>
<#macro userProfileFormFields>
    <#local currentGroup = "">
    <#list profile.attributes as attribute>
        <#if attribute.name == 'locale' && realm.internationalizationEnabled && locale.currentLanguageTag?has_content>
            <input type="hidden" id="${attribute.name}" name="${attribute.name}" value="${locale.currentLanguageTag}">
        <#else>
            <#local group = (attribute.group.name)!"">
            <#if group != currentGroup>
                <#local currentGroup = group>
                <#if group?has_content>
                    <p class="kicker" id="header-${group}">${advancedMsg(attribute.group.displayHeader!group)}</p>
                    <#if (attribute.group.displayDescription)?has_content>
                        <p class="lead" id="description-${group}">${advancedMsg(attribute.group.displayDescription)}</p>
                    </#if>
                </#if>
            </#if>
            <#nested "beforeField" attribute>
            <@field.attribute attribute=attribute/>
            <#nested "afterField" attribute>
        </#if>
    </#list>
    <@field.profileScripts/>
</#macro>
