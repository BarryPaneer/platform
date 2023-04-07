import React from 'react'
import ReactDOM from 'react-dom'
import Dropdown from 'lt-react-dropdown'
import Switch from 'react-switch'
import {QuestionMark} from '../QuestionMark'


export function mountBatchEnrollment (props, selector) {
    ReactDOM.render(
        React.createElement(BatchEnrollment, props, null),
        document.querySelector(selector)
    )
}

function BatchEnrollment ({
    courses,
    programs = [{}],
    urls,
    platformName = 'platform',
}) {
    const [targetType, setTargetType] = React.useState('Course')
    const [target, setTarget] = React.useState('')
    const [targetChoices, setTargetChoices] = React.useState(courses)
    const targetTypeChoices = [
        {value: 'Course', text: gettext('Course')},
        {value: 'Learning Path', text: gettext('Learning Path')},
    ]

    const handleSelectTarget = React.useCallback(({value}) => {
        setTarget(value)
    }, [])
    const handleSelectTargetType = React.useCallback(({value}) => {
        setTarget('')
        setTargetType(value)
        setTargetChoices(value === 'Course' ? courses : programs)
    }, [])

    const [emailsText, setEmailsText] = React.useState('')
    const handleEmailsTextChange = React.useCallback(({target: {value}}) => {
        setEmailsText(value)
    }, [])
    const [autoEnroll, setAutoEnroll] = React.useState(true)
    const [notifyByEmail, setNotifyByEmail] = React.useState(false)

    const [infoGroups, setInfoGroups] = React.useState([])
    const [errorGroups, setErrorGroups] = React.useState([])

    const postRequest = (url, data) => new Promise((resolve, reject) => $.ajax({
        dataType: 'json',
        type: 'POST',
        url,
        data,
        success: resolve,
        error: reject,
    }))

    const parseResults = React.useCallback(results => {
        const infoGroups = []
        const errorGroups = []

        const invalidIdentifier = []
        const partialUnenrollIdentifier = []
        const errors = []
        const enrolled = []
        const autoenrolled = []
        const allowed = []

        results.forEach(result => {
            if (result.invalidIdentifier) {
                invalidIdentifier.push(result)
            } else if (result.partialUnenrollIdentifier) {
                partialUnenrollIdentifier.push(result)
            } else if (result.error) {
                errors.push(result)
            } else if (result.after.enrollment) {
                enrolled.push(result)
            } else if (result.after.allowed) {
                if (result.after.auto_enroll) autoenrolled.push(result)
                else allowed.push(result)
            }
        })

        if (invalidIdentifier.length) errorGroups.push({
            title: gettext('The following email addresses and/or usernames are invalid:'),
            errors: invalidIdentifier.map(result => result.identifier),
        })
        if (partialUnenrollIdentifier.length) errorGroups.push({
            title: gettext('The following email addresses and/or usernames are needed to unenroll from learning path(s) first:'),
            errors: partialUnenrollIdentifier.map(result => result.identifier),
        })
        if (errors.length) errorGroups.push({
            title: gettext('There was an error enrolling/unenrolling:'),
            errors: errors.map(result => result.identifier),
        })
        if (enrolled.length) infoGroups.push({
            title: gettext(`Successfully enrolled ${notifyByEmail ? 'and sent email to ' : ''}the following users:`),
            infos: enrolled.map(result => result.identifier),
        })
        if (allowed.length) infoGroups.push({
            title: gettext('These users will be allowed to enroll once they register:'),
            infos: allowed.map(result => result.identifier),
        })
        if (autoenrolled.length) infoGroups.push({
            title: gettext('These users will be enrolled once they register:'),
            infos: autoenrolled.map(result => result.identifier),
        })

        return {infoGroups, errorGroups}
    }, [notifyByEmail])

    const handleUnEnroll = React.useCallback(() => {
        setInfoGroups([])
        setErrorGroups([])

        const url = targetType === 'Course' ? urls.course_enroll_button_url : urls.program_enroll_button_url
        const data = {
            action: 'unenroll',
            identifiers: emailsText,
            [targetType === 'Course' ? 'course_id' : 'program_id']: target,
            auto_enroll: autoEnroll,
            email_students: notifyByEmail,
        }

        postRequest(url, data).then(({results}) => {
            const {infoGroups, errorGroups} = parseResults(results)
            const notunenrolled = []
            const notenrolled = []

            results.forEach(result => {
                if (
                    !result.invalidIdentifier &&
                    !result.partialUnenrollIdentifier &&
                    !result.error &&
                    !result.after.enrollment &&
                    !result.after.allowed &&
                    !result.before.enrollment &&
                    !result.before.allowed
                ) {
                    notunenrolled.push(result)
                } else if (!result.after.enrollment) {
                    notenrolled.push(result);
                }
            })
            if (notunenrolled.length) errorGroups.push({
                title: gettext(`These users were not affiliated with the ${targetType === 'Course' ? 'course' : 'learning path'} so could not be unenrolled:`),
                errors: notunenrolled.map(result => result.identifier)
            })
            if (notenrolled.length) infoGroups.push({
                title: gettext(`The following users are no longer enrolled in the ${targetType === 'Course' ? 'course' : 'learning path'}:`),
                infos: notenrolled.map(result => result.identifier),
            })

            setInfoGroups(infoGroups)
            setErrorGroups(errorGroups)
        }).catch(error => {
            setErrorGroups([{
                title: gettext('Error unenrolling users.'),
                errors: [],
            }])
        })
    }, [target, targetType, autoEnroll, notifyByEmail, emailsText])

    const handleEnroll = React.useCallback(() => {
        setInfoGroups([])
        setErrorGroups([])

        const url = targetType === 'Course' ? urls.course_enroll_button_url : urls.program_enroll_button_url
        const data = {
            action: 'enroll',
            identifiers: emailsText,
            [targetType === 'Course' ? 'course_id' : 'program_id']: target,
            auto_enroll: autoEnroll,
            email_students: notifyByEmail,
        }

        postRequest(url, data).then(({results}) => {
            const {infoGroups, errorGroups} = parseResults(results)

            setInfoGroups(infoGroups)
            setErrorGroups(errorGroups)
        }).catch(error => {
            setErrorGroups([{
                title: gettext('Error enrolling/unenrolling users.'),
                errors: [],
            }])
        })
    }, [target, targetType, autoEnroll, notifyByEmail, emailsText])

    const formatPlatformName = s => s.replace('{em_start}', '').replace('{em_end}', '').replace('{platform_name}', platformName)

    return (
        <>
            <div className="setting selectors">
                {!!programs.length && (
                    <div className="selector select-wrapper">
                        <label>{gettext('Select Enroll Type:')}</label>
                        <Dropdown sign="caret" value={targetType} data={targetTypeChoices} onChange={handleSelectTargetType} />
                    </div>
                )}
                <div className="selector select-wrapper">
                    <label>{gettext(`Select a ${targetType}:`)}</label>
                    <Dropdown sign="caret" searchable value={target} data={targetChoices} onChange={handleSelectTarget} />
                </div>
            </div>

            {!!target && (
                <div className="setting batch-enrollment">
                    <legend>{gettext('Enter email addresses and/or usernames separated by new lines or commas.')}</legend>
                    <textarea placeholder={gettext('Email Address')} value={emailsText} rows="3" onChange={handleEmailsTextChange} />

                    <BatchResults errorGroups={errorGroups} infoGroups={infoGroups} />

                    <div className="checkbox">
                        <label>{gettext('Auto Enroll')}</label>
                        <Switch onChange={setAutoEnroll} checked={autoEnroll} width={40} checkedIcon={false} uncheckedIcon={false} onColor={"#e7413c"} />
                        <QuestionMark tooltip={
                            formatPlatformName(gettext("If this option is {em_start}checked{em_end}, users who have not yet registered for {platform_name} will be automatically enrolled.")) + ' ' +
                            formatPlatformName(gettext("If this option is left {em_start}unchecked{em_end}, users who have not yet registered for {platform_name} will not be enrolled, but will be allowed to enroll once they make an account.")) + ' ' +
                            gettext("Checking this box has no effect if 'Unenroll' is selected.")
                        } />
                    </div>
                    <div className="checkbox">
                        <label>{gettext('Notify user by email')}</label>
                        <Switch onChange={setNotifyByEmail} checked={notifyByEmail} width={40} checkedIcon={false} uncheckedIcon={false} onColor={"#e7413c"} />
                        <QuestionMark tooltip={formatPlatformName(gettext("If this option is {em_start}checked{em_end}, users will receive an email notification."))} />
                    </div>

                    <div class="actions">
                        <button type="button" onClick={handleUnEnroll} class="lt-btn btn-grey">
                            <span>{gettext("Unenroll")}</span>
                        </button>
                        <button type="button" onClick={handleEnroll} class="lt-btn btn-primary">
                            <span>{gettext("Enroll")}</span>
                        </button>
                    </div>
                </div>
            )}
        </>
    )
}


function BatchResults ({errorGroups, infoGroups}) {
    return (
        <div class="results">
            {!!errorGroups.length && (
                <div class="errors">
                    {errorGroups.map((errorGroup, index) => (
                        <div key={index}>
                            <strong>{errorGroup.title}</strong>
                            {errorGroup.errors.map((error, j) => <p key={j}>{error}</p>)}
                        </div>
                    ))}
                </div>
            )}
            {!!infoGroups.length && (
                <div class="infos">
                    {infoGroups.map((infoGroup, index) => (
                        <div>
                            <strong>{infoGroup.title}</strong>
                            {infoGroup.infos.map((info, j) => <p key={j}>{info}</p>)}
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
