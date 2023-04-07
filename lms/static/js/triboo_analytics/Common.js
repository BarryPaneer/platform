import React from "react";

const LastUpdate = function (props) {
    return (<p className="last-update">
        <span
            className="far fa-sync-alt"></span>{gettext('Please, note that these reports are not live. Last update:')} {props.last_update}
    </p>)
}

const StatusRender = (value) => {
    let statusConfig = {
        'Not Started': 'not-started-bg',
        'In Progress': 'in-progress-bg',
        'Successful': 'finished-bg',
        'Unsuccessful': 'failed-bg'
    }
    return <span className={statusConfig[value]}>{gettext(value)}</span>

}, PercentRender = value => {
    return value && value.indexOf('%') < 0 ? `${value}%` : value

}

const DatalistToolbarFooter = ({lastUpdate, onApply, disabled}) => (
  <p className="last-update">
      <span className="far fa-sync-alt"></span>{gettext('Please, note that these reports are not live. Last update:')} {lastUpdate}
      <input type="button" className="apply-trigger" value={gettext('Apply')} onClick={onApply} disabled={disabled}></input>
  </p>
)

export {LastUpdate,StatusRender,PercentRender, DatalistToolbarFooter}
