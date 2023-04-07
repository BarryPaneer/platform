function mountCsvRegistration ({urls}, el) {
    const BatchResults = {
        template: `
            <div class="results">
                <div class="errors" v-if="errorGroups.length">
                    <div v-for="errorGroup in errorGroups">
                        <strong>{{errorGroup.title}}</strong>
                        <p v-for="error in errorGroup.errors">{{error}}</p>
                    </div>
                </div>
                <div class="infos" v-if="infoGroups.length">
                    <div v-for="infoGroup in infoGroups">
                        <strong>{{infoGroup.title}}</strong>
                        <p v-for="info in infoGroup.infos">{{info}}</p>
                    </div>
                </div>
            </div>
        `,
        props: {
            errorGroups: Array,
            infoGroups: Array,
        }
    }

    return new Vue({
        el,
        components: {
            BatchResults,
        },
        data () {
            return {
                urls,
                registrationFile: null,
                registrationInfoGroups: [],
                registrationErrorGroups: [],
                updateFile: null,
                updateInfoGroups: [],
                updateErrorGroups: [],
                emailsText: '',
                emailInfoGroups: [],
                emailErrorGroups: [],
            }
        },
        created () {
        },
        methods: {
            handleRegistrationFileChange (e) {
                this.resetRegisterResults()
                this.registrationFile = e.target.files[0]
            },
            handleDropRegistrationFile (e) {
                e.preventDefault()
                this.resetRegisterResults()
                this.registrationFile = e.dataTransfer.files[0]
            },
            clearRegistrationFile () {
                this.registrationFile = null
                this.resetRegisterResults()
            },
            handleTestCsvFile (e) {
                e.preventDefault()
                this.resetRegisterResults()
                if (!this.registrationFile) {
                    this.registrationErrorGroups = [{
                        title: gettext('Errors'),
                        errors: [
                            gettext('File not attached'),
                        ]
                    }]
                    return
                }

                const url = this.urls.precheck_upload_student_csv_button_url
                const data = new FormData()
                data.append('students_list', this.registrationFile)

                this.postRequest(url, data).then(response => {
                    this.registrationInfoGroups = [{
                        title: gettext('CSV file ready for upload'),
                        infos: [],
                    }]
                }).catch(response => {
                    this.registrationErrorGroups = [{
                        title: gettext('Errors'),
                        errors: (response.general_errors || response.row_errors || []).map(r => r.response),
                    }]
                })
            },
            handleRegister (e) {
                e.preventDefault()
                this.resetRegisterResults()
                if (!this.registrationFile) {
                    this.registrationErrorGroups = [{
                        title: gettext('Errors'),
                        errors: [
                            gettext('File not attached'),
                        ]
                    }]
                    return
                }

                const url = this.urls.upload_student_csv_button_url
                const data = new FormData()
                data.append('students_list', this.registrationFile)

                this.postRequest(url, data).then(response => {
                    try {
                        const infoGroups = []
                        if (response.created.length) infoGroups.push({
                            title: gettext('Users successfully created:'),
                            infos: response.created.map(r => r.response)
                        })
                        if (response.untouched.length) infoGroups.push({
                            title: gettext('Users who were already registered (no changes):'),
                            infos: response.untouched.map(r => r.response)
                        })
                        const errors = [].concat(response.general_errors || []).concat(response.row_errors || []).map(r => r.response)
                        if (errors.length) {
                            this.registrationErrorGroups = [{
                                title: gettext('Errors'),
                                errors,
                            }]
                        }
                        this.registrationInfoGroups = infoGroups
                    } catch (error) {
                        throw response
                    }
                }).catch(response => {
                    console.error(response)
                    const errors = [].concat(response.general_errors || []).concat(response.row_errors || []).map(r => r.response)
                    if (errors.length) {
                        this.registrationErrorGroups = [{
                            title: gettext('Errors'),
                            errors,
                        }]
                    }
                })
            },

            handleUpdateFileChange (e) {
                this.resetUpdateResults()
                this.updateFile = e.target.files[0]
            },
            handleDropUpdateFile (e) {
                e.preventDefault()
                this.resetUpdateResults()
                this.updateFile = e.dataTransfer.files[0]
            },
            clearUpdateFile () {
                this.updateFile = null
                this.resetUpdateResults()
            },
            handleUpdate (e) {
                e.preventDefault()
                this.resetUpdateResults()
                if (!this.updateFile) {
                    this.updateErrorGroups = [{
                        title: gettext('Errors'),
                        errors: [
                            gettext('File not attached'),
                        ]
                    }]
                    return
                }

                const url = this.urls.update_student_csv_button_url
                const data = new FormData()
                data.append('students_list', this.updateFile)

                this.postRequest(url, data).then(response => {
                    if (response.updated.length) {
                        this.updateInfoGroups = [{
                            title: gettext('User accounts successfully updated:'),
                            infos: response.updated.map(r => r.response),
                        }]
                    } else throw response
                }).catch(response => {
                    console.error(response)
                    const errors = [].concat(response.general_errors || []).concat(response.row_errors || []).map(r => r.response)
                    if (errors.length) {
                        this.updateErrorGroups = [{
                            title: gettext('Errors'),
                            errors,
                        }]
                    }
                })
            },

            handleSendEmails (e) {
                e.preventDefault()
                this.resetEmailResults()

                const url = this.urls.send_welcoming_email_url
                const data = new FormData()
                data.append('emails', this.emailsText)

                this.postRequest(url, data).then(response => {
                    if (response.row_successes.length) {
                        this.emailInfoGroups = [{
                            title: gettext("Successfully sent welcoming emails to the following addresses:"),
                            infos: response.row_successes,
                        }]
                    }

                    if (response.row_errors.length) {
                        this.emailErrorGroups = [{
                            title: gettext('The following email addresses are invalid:'),
                            errors:  response.row_errors,
                        }]
                    }
                }).catch(response => {
                    console.error(response)
                })
            },

            resetRegisterResults () {
                this.registrationInfoGroups = []
                this.registrationErrorGroups = []
            },
            resetUpdateResults () {
                this.updateErrorGroups = []
                this.updateInfoGroups = []
            },
            resetEmailResults () {
                this.emailErrorGroups = []
                this.emailInfoGroups = []
            },

            async postRequest (url, data) {
                return new Promise((resolve, reject) => {
                    $.ajax({
                        dataType: 'json',
                        type: 'POST',
                        processData: false,
                        contentType: false,
                        url,
                        data,
                        success: resolve,
                        error: reject,
                    })
                })
            }
        },
    })
}
