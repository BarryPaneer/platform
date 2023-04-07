import React from 'react';
import {PaginationConfig} from "./Config";
import {get, merge, omit, isEmpty, pick} from "lodash";


export default class BaseReport extends React.Component{
    constructor(props) {
        super(props)
        this.state = {
            timer:null,

            isLoading:false,
            properties:[],

            //storing toolbar data
            toolbarData: props.defaultToolbarData || {},

            //ajax result
            message:'',
            columns:[],
            data: [],
            totalData: {},
            rowsCount: 0,
            xhrFetchData: null,
            fields: [],
            subFields: undefined,
            applyDisabled: true,
        }

        this.myRef = React.createRef()
    }

    componentDidMount() {
        this.fetchData(1)
        this.updateFields()
    }

    getFields () {
        const propertiesFields = this.getOrderedProperties()
        const {dynamicFields, subFields} = this.getDynamicFields()
        return {
            fields: [
                {name: gettext('Name'), fieldName: 'Name', render:(value)=>{
                    return <div dangerouslySetInnerHTML={{__html: value}} />
                }},

                ...propertiesFields,

                ...dynamicFields,
            ],
            subFields,
        }
    }

    getDynamicFields () {
        return {
            dynamicFields: [],
        }
    }

    updateFields () {
        this.setState(this.getFields())
    }

    /**
     * @param {Boolean} isExcluded prevent auto applying query
     */
    toolbarDataUpdate(toolbarData, isExcluded) {
        this.setState(prev => ({
            toolbarData,
            applyDisabled: isExcluded === true && prev.applyDisabled,
        }), () => {
            if (!isExcluded) this.applyQuery()

            const {onChange} = this.props
            onChange && onChange(this.state.toolbarData)
        })
    }

    applyQuery () {
        this.fetchData(1)
        this.updateFields()
        this.myRef.current.resetPage(1)
        this.setState({
            applyDisabled: true,
        })
    }

    getOrderedProperties() {
        const propertyOrder = {
            'user_first_name': 0,
            'user_last_name': 1,
            'user_username': 2,
            'user_lt_employee_id': 3,
            'user_email': 4,
            'user_date_joined': 5,
            'user_gender': 6,
            'user_year_of_birth': 7,
            'user_country': 8,
            'user_lt_area': 9,
            'user_lt_sub_area': 10,
            'user_city': 11,
            'user_location': 12,
            'user_lt_address': 13,
            'user_lt_address_2': 14,
            'user_lt_phone_number': 15,
            'user_lt_gdpr': 16,
            'user_lt_company': 17,
            'user_lt_hire_date': 18,
            'user_lt_level': 19,
            'user_lt_job_description': 20,
            'user_lt_job_code': 21,
            'user_lt_department': 22,
            'user_lt_supervisor': 23,
            'user_lt_ilt_supervisor': 24,
            'user_mailing_address': 25,
            'user_lt_learning_group': 26,
            'user_lt_exempt_status': 27,
            'user_lt_comments': 28
        }
        const {data}=this.state;
        const {selectedProperties}=this.state.toolbarData;
        const properties = selectedProperties && selectedProperties.length
            ? selectedProperties
            : this.state.properties.filter(p => p.type === 'default')

        let orderedProperties = []
        if (data && data.length > 0) {
            const firstRow = data[0]
            const propertiesValues = properties.map(p=>p.value)
            orderedProperties = Object.keys(firstRow)
                .filter(key => propertiesValues.includes(key))
                .map(key=>{
                    const item = properties.find(p=>p.value == key)
                    return item || {text:key, value:key}
                });
        }
        const propertiesFieldsToBeTranslate = ['user_country', 'user_gender']
        return (orderedProperties.length > 0 ? orderedProperties : properties)
            .sort(function(a, b) {
                return propertyOrder[a.value] >= propertyOrder[b.value] ? 1 : -1;
            })
            .map(p=>({
                name: p.text,
                fieldName: p.value,
                render:(cellValue, row, item)=>{
                    let finalVal = (cellValue == null || cellValue === '') ? '—' :
                        (propertiesFieldsToBeTranslate.includes(item.fieldName) ? gettext(cellValue) : cellValue.toString())
                    return finalVal
                }
            }));
    }

    generateParameter () {
        const {toolbarData} = this.state
        const getVal = (key, defaultValue) => {
            return toolbarData && toolbarData[key] ? toolbarData[key] : defaultValue || ''
        }

        return {
            report_type: get(this.setting, 'reportType', ''),
            query_tuples: get(toolbarData, 'selectedFilterItems', []).map(p => [p.value, p.key]),
            selected_properties: get(toolbarData, 'selectedProperties', []).map(p => p.value),
            from_day: getVal('startDate'),
            to_day: getVal('endDate'),
            csrfmiddlewaretoken: this.props.token,
            page: {
                size: this.props.pageSize || PaginationConfig.PageSize
            },
            ...get(this.setting, 'extraParams', {}),
        }
    }

    getBaseConfig() {
        return {
            onSort:(sort, pageNo)=>{
                sort == '' ?
                    this.fetchData(pageNo) :
                    this.fetchData(pageNo, sort)
            },
            onPageChange:(pageNo, sort)=>{
                sort == '' ?
                    this.fetchData(pageNo) :
                    this.fetchData(pageNo, sort)
            },
            ...pick(this.state, ['isLoading', 'data', 'totalData', 'message']),
            totalRowsText:gettext('Total: * rows'),
            emptyText:gettext('No data available'),
            pagination: {
                pageSize: PaginationConfig.PageSize,
                rowsCount: this.state.rowsCount,
            }
        }
    }

    fetchData(pageNo, sort='+ID') {
        const url = get(this.setting, 'dataUrl', '')
        let ajaxData = merge(this.generateParameter(), {
            page: {
                no: pageNo
            },
            sort: sort || undefined,
        })

        const isValidateDate = v => {
          if (!v) return true
          if (isNaN(new Date(v).getTime())) return false
          return true
        }

        if (!isValidateDate(ajaxData.from_day)) return
        if (!isValidateDate(ajaxData.to_day)) return

        const xhrFetchData = $.ajax(url, {
            // method: 'get', //please change it to post in real environment.
            method: 'post',
            contentType: 'application/json; charset=utf-8',
            data: JSON.stringify(ajaxData),
            dataType: 'json',
            beforeSend: () => {
              if (this.state.xhrFetchData) this.state.xhrFetchData.abort()
              this.setState(() => ({
                xhrFetchData,
                isLoading: true
              }))
            },
            success: (json) => {
                this.setState((s, p) => {
                    return {
                        message: json.message,
                        isLoading:false,
                        data: json.list,
                        columns:json.columns,
                        totalData: json.total, //{email: 'total:', first_name: json.total},
                        rowsCount: json.pagination.rowsCount
                    }
                }, this.updateFields)
            },
            error:(json)=>{
                this.setState((s, p) => {
                    return {
                        message: get(json, 'responseJSON.message', ''),
                        isLoading:false
                    }
                })
            }
        })
    }

    startExport(type) {
        const url = `/analytics/export/`
        let ajaxData = omit({
            ...this.generateParameter(),
            format: type,
            report_type:get(this.setting, 'reportType', '')
        }, 'page')
        const showMessage = (result)=>{
            LearningTribes.dialog.show(result.message, 3000)
        }
        $.ajax(url, {
            // method: 'get', //please change it to post in real environment.
            method: 'post',
            contentType: 'application/json; charset=utf-8',
            data: JSON.stringify(ajaxData),
            dataType: 'json',
            success: showMessage,
            error:showMessage
        })
    }
}
