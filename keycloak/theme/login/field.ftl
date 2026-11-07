<#-- The app's fields (frontend/src/ui/components.tsx, Field): the label in mono capitals, a square
     input, then its hint and its error, both named by the input's aria-describedby. Forms use
     novalidate, as in the app: `required` only tells assistive technologies. -->

<#-- A field. `error` is a message from messagesPerField, which may hold sanitized HTML;
     `invalid` marks a field whose error is shown elsewhere (the sign-in's note). -->
<#macro input name label id=name type="text" value="" autocomplete="" hint="" error="" invalid=false autofocus=false required=true disabled=false dir="" data={}>
    <div class="field">
        <label for="${id}" class="field-label">${label}</label>
        <input id="${id}" name="${name}" type="${type}" class="field-input" value="${value}"<#if autocomplete?has_content> autocomplete="${autocomplete}"</#if><#if autofocus> autofocus</#if><#if required> required</#if><#if disabled> disabled</#if><#if dir?has_content> dir="${dir}"</#if><#list data as key, val> data-${key}="${val}"</#list><@describedBy id=id hint=hint error=error invalid=invalid/>>
        <@notes id=id hint=hint error=error/>
    </div>
</#macro>

<#-- A new password, typed once as in the app. Keycloak also wants it in password-confirm:
     sibylle.js copies it there on submit, and without JavaScript a second field asks for it. -->
<#macro newPassword name label hint="" error="" confirmError="" autofocus=false>
    <@input name=name label=label type="password" autocomplete="new-password" hint=hint error=error autofocus=autofocus data={"confirmed-by": "password-confirm"}/>
    <noscript>
        <@input name="password-confirm" label=msg("passwordConfirm") type="password" autocomplete="new-password" error=confirmError/>
    </noscript>
</#macro>

<#-- The realm's user profile in the app's order (AuthPages.tsx, SignupPage): first and last names
     side by side with the note that they stay private, then the e-mail, then what the page
     nests (the sign-up's password), then any other field the profile has. -->
<#macro profileFields>
    <#local byName = profile.attributesByName>
    <#local placed = ["firstName", "lastName", "username", "email", "locale"]>
    <#if byName.firstName?? && byName.lastName??>
        <div class="row">
            <@attribute attribute=byName.firstName/>
            <@attribute attribute=byName.lastName/>
        </div>
        <span class="note">${msg("sibylle.privateNames")}</span>
    <#else>
        <#list ["firstName", "lastName"] as name>
            <#if byName[name]??><@attribute attribute=byName[name]/></#if>
        </#list>
    </#if>
    <#if byName.username?? && !realm.registrationEmailAsUsername><@attribute attribute=byName.username/></#if>
    <#if byName.email??><@attribute attribute=byName.email/></#if>
    <#nested>
    <#if byName.locale?? && realm.internationalizationEnabled && locale.currentLanguageTag?has_content>
        <input type="hidden" id="locale" name="locale" value="${locale.currentLanguageTag}">
    </#if>
    <#list profile.attributes as other>
        <#if !placed?seq_contains(other.name)><@attribute attribute=other/></#if>
    </#list>
    <@profileScripts/>
</#macro>

<#-- A field of the realm's user profile (the base theme's user-profile-commons.ftl,
     inputFieldByType): text inputs as the app's fields, lists and choices in the same frame. -->
<#macro attribute attribute autofocus=false>
    <#local name = attribute.name>
    <#local label = advancedMsg(attribute.displayName!'')>
    <#local error = errorOf(name)>
    <#local hint = "">
    <#if attribute.annotations.inputHelperTextAfter??>
        <#local hint = advancedMsg(attribute.annotations.inputHelperTextAfter)>
    </#if>
    <#local inputType = attribute.annotations.inputType!"">
    <#if inputType == "textarea">
        <div class="field">
            <label for="${name}" class="field-label">${label}</label>
            <textarea id="${name}" name="${name}" class="field-input"<#if attribute.required> required</#if><#if attribute.readOnly> disabled</#if><@describedBy id=name hint=hint error=error/>>${attribute.value!''}</textarea>
            <@notes id=name hint=hint error=error/>
        </div>
    <#elseif inputType == "select" || inputType == "multiselect">
        <div class="field">
            <label for="${name}" class="field-label">${label}</label>
            <select id="${name}" name="${name}" class="field-input"<#if inputType == "multiselect"> multiple</#if><#if attribute.required> required</#if><#if attribute.readOnly> disabled</#if><@describedBy id=name hint=hint error=error/>>
                <#if inputType == "select"><option value=""></option></#if>
                <#list options(attribute) as option>
                    <option value="${option}"<#if attribute.values?seq_contains(option)> selected</#if>>${optionLabel(attribute, option)}</option>
                </#list>
            </select>
            <@notes id=name hint=hint error=error/>
        </div>
    <#elseif inputType == "select-radiobuttons" || inputType == "multiselect-checkboxes">
        <fieldset class="field"<@describedBy id=name hint=hint error=error/>>
            <legend class="field-label">${label}</legend>
            <#list options(attribute) as option>
                <label class="checkbox">
                    <input type="${(inputType == 'select-radiobuttons')?then('radio', 'checkbox')}" name="${name}" value="${option}"<#if attribute.values?seq_contains(option)> checked</#if><#if attribute.readOnly> disabled</#if>>
                    ${optionLabel(attribute, option)}
                </label>
            </#list>
            <@notes id=name hint=hint error=error/>
        </fieldset>
    <#else>
        <#local type = "text">
        <#if inputType?starts_with("html5-")>
            <#local type = inputType[6..]>
        <#elseif inputType?has_content>
            <#local type = inputType>
        <#elseif name == "email">
            <#local type = "email">
        </#if>
        <#local dir = "">
        <#if name == "email" || name == "username"><#local dir = "ltr"></#if>
        <@input name=name label=label type=type value=(attribute.value!'') autocomplete=(attribute.autocomplete!'') hint=hint error=error autofocus=autofocus required=attribute.required disabled=attribute.readOnly dir=dir data=attribute.html5DataAnnotations/>
    </#if>
</#macro>

<#-- The scripts some profile fields ask for (the base theme's kcMultivalued.js…). -->
<#macro profileScripts>
    <#list profile.html5DataAnnotations?keys as key>
        <script type="module" src="${url.resourcesPath}/js/${key}.js"></script>
    </#list>
</#macro>

<#-- The sign-in name's label: the e-mail address for Sibylle, whose realm signs in by e-mail. -->
<#function usernameLabel>
    <#if !realm.loginWithEmailAllowed>
        <#return msg("username")>
    <#elseif !realm.registrationEmailAsUsername>
        <#return msg("usernameOrEmail")>
    </#if>
    <#return msg("email")>
</#function>

<#-- A field's error, or nothing. -->
<#function errorOf name>
    <#if messagesPerField.existsError(name)>
        <#return messagesPerField.get(name)>
    </#if>
    <#return "">
</#function>

<#function options attribute>
    <#local from = attribute.annotations.inputOptionsFromValidation!"">
    <#if from?has_content && attribute.validators[from]?? && attribute.validators[from].options??>
        <#return attribute.validators[from].options>
    <#elseif attribute.validators.options?? && attribute.validators.options.options??>
        <#return attribute.validators.options.options>
    </#if>
    <#return []>
</#function>

<#function optionLabel attribute option>
    <#if attribute.annotations.inputOptionLabels??>
        <#return advancedMsg(attribute.annotations.inputOptionLabels[option]!option)>
    <#elseif attribute.annotations.inputOptionLabelsI18nPrefix??>
        <#return msg(attribute.annotations.inputOptionLabelsI18nPrefix + '.' + option)>
    </#if>
    <#return option>
</#function>

<#macro describedBy id hint="" error="" invalid=false>
    <#local described = []>
    <#if hint?has_content><#local described = described + [id + "-hint"]></#if>
    <#if error?has_content><#local described = described + [id + "-error"]></#if>
    <#if described?has_content> aria-describedby="${described?join(' ')}"</#if><#if error?has_content || invalid> aria-invalid="true"</#if><#t>
</#macro>

<#macro notes id hint="" error="">
    <#if hint?has_content><span id="${id}-hint" class="field-hint">${hint}</span></#if>
    <#if error?has_content><span id="${id}-error" class="field-error" role="alert">${kcSanitize(error)?no_esc}</span></#if>
</#macro>
