import React from 'react'

function ExploreBlock (pr) {
    return (
        <div className={`explore-block ${pr.theme || 'star-wall'}`}>
            {pr.subTitle !== false && <small><i/><span>{gettext(pr.subTitle || 'Begin a Course or a Learning Path now')}</span><i/></small>}
            <h4>{gettext(pr.title || 'You are not enrolled in any Trainings yet.')}</h4>
            {pr.explore !== false && <a href={pr.url || '#'}>{gettext('Explore')}</a>}
        </div>
    )
}
export {ExploreBlock}
