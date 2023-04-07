import React from "react";

// styling _common.scss inside lms of triboo-theme project
class TabsTitle extends React.Component {
    constructor(props) {
        super(props);

        const {activeValue, data}=this.props
        this.state = {
            activeValue:activeValue || (data && data.length ? data[0].value : '')
        };
    }

    activeNav(e, item){
        const activeValue = item.value
        this.setState({activeValue}, ()=>{
            const {onChange, data}=this.props
            onChange && onChange(e, data.find(p=>p.value == activeValue))
        })
    }

    render(){
        const pr=this.props
        const {activeValue} = this.state

        return <ul className={pr.className ? pr.className : 'tabs-title'}>
            {pr.data.map(p => (
                <li key={p.value} onClick={e=>this.activeNav(e, p)}
                    title={p.description}
                    className={`${pr.itemClassName ? pr.itemClassName  : 'tabs-title-item'}  ${p.value}${(p.value == activeValue ? (pr.activeItemClassName ? ' '+pr.activeItemClassName : ' active')  : '')}`}>{gettext(p.text)}</li>
            ))}
        </ul>
    }
}
export {TabsTitle}
