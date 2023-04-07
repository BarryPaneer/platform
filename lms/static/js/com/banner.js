import React from 'react'
import {Tabs, Module} from './tabs'


const Switcher = () => {
    return (
        <a>
            <span className="switcher">
                <span className="round-button active">{gettext("Internal")}</span>
                <span className="round-button">{gettext("External")}</span>
            </span>
        </a>
    )
}

class Banner extends React.Component {
    constructor (props) {
        super(props)
    }

    render () {
        const pr = this.props
        return <section className="banner my-training-banner">
            <section className="welcome-wrapper">
                <h2>{pr.module == Module.myTraining ? gettext("My Training") : gettext("Explore")}</h2>
                {pr.switcher && <Switcher />}
            </section>
            {!!pr.showTabs && <Tabs module={pr.module} />}
        </section>
    }
}

export {Banner}
