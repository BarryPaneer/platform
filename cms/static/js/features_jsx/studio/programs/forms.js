import React from 'react'
import Dropdown from "lt-react-dropdown"

import {QuestionMark} from "../../../../../../lms/static/js/QuestionMark"
import EditingForm from './editing-form'


function CreatingForm ({onCancel, onSave, data}) {
    const [formData, setFormData] = React.useState({
        title: '',
        partner: ((data || [])[0]) || '',
    })
    const [errorMessage, setErrorMessage] = React.useState('')

    const handlePathNameChange = event => {
        const title = event.target.value
        setFormData(prev => ({
            ...prev,
            title,
        }))
    }
    const handleOrgChange = option => setFormData(prev => ({
        ...prev,
        partner: option.value,
    }))

    const handleSubmit = React.useCallback(e => {
        onSave(e, formData)
        e.preventDefault()
        return false
    }, [formData, onSave])

    const isFormValid = React.useMemo(() => !!formData.title && formData.partner, [formData])

    return (
        <form className="form-create create-path path-info is-shown" id="create-path-form"
            name="create-path-form">

            <div className={"wrap-error" + (errorMessage != '' ? ' is-shown' : '')}>
                <div id="path_creation_error" name="path_creation_error"
                    className="message message-status message-status error" role="alert">
                    <p>{errorMessage}</p>
                </div>
            </div>

            <div className="wrapper-form">
                <h3 className="title">{gettext("Create a New Path")}</h3>

                <fieldset>
                    <legend className="sr">{gettext("Required Information to Create a New Path")}</legend>

                    <ol className="list-input">
                        <li className="field text required" id="field-path-name">
                            <label htmlFor="new-path-name">{gettext("Path Name")}</label>
                            <input className="new-path-name fixed_width_350px" id="new-path-name" type="text" name="new-path-name"
                                required
                                placeholder={gettext('e.g. An learning path')}
                                aria-describedby="tip-new-path-name tip-error-new-path-name"
                                onChange={handlePathNameChange}
                            />
                            <QuestionMark className="question-mark" tooltip={gettext("The public display name for your learning path. This cannot be changed, but you can set a different display name in Advanced Settings later.")} />
                            <span className="tip" id="tip-new-path-name">{gettext("The public display name for your learning path. This cannot be changed, but you can set a different display name in Advanced Settings later.")}</span>
                            <span className="tip tip-error is-hiding" id="tip-error-new-path-name"></span>
                        </li>
                        <li className="field text required" id="field-path-org">
                            <label htmlFor="new-path-org">{gettext("Organization")}</label>
                            <Dropdown
                                data={(data.length > 0 && Object.keys(data[0]).length > 0 ? data : []).map(p => ({text: p, value: p}))}
                                value={formData.partner}
                                onChange={handleOrgChange}
                                className="fixed_width_350px"
                            />
                            <QuestionMark
                                className="question-mark"
                                tooltip={gettext("The name of the organization sponsoring the learning path. You can also set a different display name in Advanced Settings later.").replace("{strong_start}", "<strong>").replace("{strong_end}", "</strong>")}
                            />
                            <span className="select-wrapper"></span>
                            <span className="tip" id="tip-new-path-org">{gettext("The name of the organization sponsoring the learning path. You can also set a different display name in Advanced Settings later.").replace("{strong_start}", "<strong>").replace("{strong_end}", "</strong>")}</span>
                            <span className="tip tip-error is-hiding" id="tip-error-new-path-org"></span>
                        </li>

                    </ol>

                </fieldset>
            </div>

            <div className="actions">
                <input type="hidden" value="False" className="allow-unicode-course-id" />
                <input type="submit" value={gettext('Create')} className={`action action-primary new-path-save${!isFormValid ? ' is-disabled' : ''}`}
                    disabled={!isFormValid}
                    onClick={handleSubmit}
                />
                <input type="button" value={gettext('Cancel')} className="action action-secondary action-cancel new-path-cancel"
                    onClick={onCancel} />
            </div>
        </form>
    )
}

export {EditingForm, CreatingForm}
