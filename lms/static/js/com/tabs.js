import React from "react";

const TabKey = { all:'all',learningPaths:'learning-paths', courses:'courses'}
const Module = {myTraining:'myTraining', explore:'explore'}
const MyTrainingLink = {
    myTraining:{
        [TabKey.all]:'my_training_overview',
        [TabKey.learningPaths]:'my_training_programs',
        [TabKey.courses]:'my_courses/all-courses',
    },
    explore:{
        [TabKey.all]:'courses_overview',
        [TabKey.learningPaths]:'programs',
        [TabKey.courses]:'courses',
    }
}
const tabs = [
    {text:'All',value:TabKey.all},
    {text:'Learning Paths',value:TabKey.learningPaths},
    {text:'Courses',value:TabKey.courses}
]

class Tabs extends React.Component {
    constructor(props) {
        super(props);
    }

    render(){
        const pr = this.props
        return <div className="category_tabs">{tabs.map(p=>{
            const path = MyTrainingLink[pr.module || 'myTraining'][p.value]
            return (
                <a key={p.value} href={`/${path}/`} className={window.location.pathname == `/${path}/` ? 'current_category' : 'categories'}>
                    <span>{gettext(p.text)}</span>
                </a>
            )
        })}</div>
    }
}

export {Tabs, Module}
