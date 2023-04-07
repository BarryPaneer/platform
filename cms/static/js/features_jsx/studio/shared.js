import React, {Component, Fragment, useState} from 'react';
import {IsDebug} from '../../../../../common/static/js/global_variable'

const Loading = () => {
    return <div className="lt-loading"><span className="far fa-spinner fa-spin"></span></div>
}

class ProgramBase extends Component {
    constructor(props) {
        super(props);
        ///?tab=program
        document.querySelector('.brand-link').setAttribute('href', '/?tab=program')
    }
}
class Info extends Component {

    constructor(props) {
        super(props)
        const pr = props
        this.state = {
            text:''
        }
        const fetchData = async (uuid) => {
            return await (await fetch(`/api/proxy/discovery/api/v1/programs/${uuid}/`)).json();
        }

        fetchData(pr.uuid).then(p=>{
            this.setState({text:p.title})
            const {onLoad}=this.props
            onLoad && onLoad(p)
        })
    }

    render(){
        const {text}=this.state
        return <Fragment>
            <span className="sr" > Current Program:</span>
            <a className="program-link" href="#">
                <span className="program-title" title={text}>{text}</span>
                {/*<span className="course-org">edX</span><span className="splinter">/</span><span className="course-number">adas</span>*/}
            </a>
        </Fragment>
    }

}
export {Loading, ProgramBase, Info, IsDebug}
