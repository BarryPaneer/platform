import React from 'react';
import ReactDOM from 'react-dom'

let mountNotification
let notificationContainer
let notificationCount = 0

function NotificationContainer () {
    const [notifications, setNotifications] = React.useState([])
    React.useEffect(() => {
        mountNotification = props => {
            const key = ++notificationCount
            //setNotifications(prev => prev.concat(Object.assign(props, {key})))
            setNotifications(()=> [Object.assign(props, {key})]) // only keep one popup at the sametime.
            return () => setNotifications(prev => prev.filter(n => n.key !== key))
        }
        return () => {
            mountNotification = null
        }
    }, [])

    return (
        <React.Fragment>
          {notifications.map(notification => <Notification {...notification} />)}
        </React.Fragment>
    )
}

const getOrCreateElementById = id => {
    const $el = document.getElementById(id)
    if ($el) return $el

    const $div = document.createElement('div')
    $div.id = id
    document.body.append($div)
    return $div
}

const NotificationFactory = type => props => {
    if (!notificationContainer) {
        notificationContainer = getOrCreateElementById('page-notification')
        ReactDOM.render(
            React.createElement(NotificationContainer, {}, null),
            notificationContainer
        )
    }

    let unmount = () => console.warn('Not mounted yet.')
    const onDispose = () => unmount()
    requestAnimationFrame(function tryMount () {
        if (mountNotification) {
            unmount = mountNotification(Object.assign(props, {type, onDispose}))
        } else requestAnimationFrame(tryMount)
    })

    return onDispose
}

export function Notification (props) {
    const [animationClassName, setAnimationClassName] = React.useState('is-shown')
    const HIDE_ANIMATION_CLASS_NAME = 'is-hiding'

    function disposeButtonClick(e, callbackName) {
        const callback = props[callbackName]
        if (callback && callback(e) === false) return;
        setAnimationClassName(HIDE_ANIMATION_CLASS_NAME)
    }

    const {type, title, message, cancelText, confirmText, icon} = props, pr=props
    const iconObj = {
        warning:'question',
        error:'exclamation-triangle',
        info:'check',
    }
    const hideActions = (cancelText == null && confirmText == null && pr.onConfirm == null && pr.onCancel == null)

    const onAnimationEnd = React.useCallback(() => {
        if (animationClassName !== HIDE_ANIMATION_CLASS_NAME) return

        const {onDispose} = props
        if (onDispose) onDispose()
    }, [animationClassName])

    return (
        <div className={`wrapper wrapper-notification wrapper-notification-${type||"warning"} ${animationClassName}`}
            id={`notification-${type||"warning"}`} tabIndex="-1"
            onAnimationEnd={onAnimationEnd}
            aria-hidden="false" aria-labelledby="notification-warning-title"
            aria-describedby="notification-warning-description" role="dialog">
            <div className="notification">
                <a href={void(0)} className="far fa-times action action-close" onClick={e=>disposeButtonClick(e, 'onCancel')}></a>
                <div>
                    <span className={`feedback-symbol fa fa-${icon || iconObj[type] || 'warning'}`} aria-hidden="true"></span>
                    <div className="copy">
                        {title && <h2 className="title">{title}</h2>}
                        <p className="message" dangerouslySetInnerHTML={{ __html: (message || '') }}></p>
                    </div>
                </div>
                <nav className={"nav-actions" + (hideActions ?' hidden':'')}>
                    <ul>
                        <li className="nav-item">
                            <button className="action-secondary" onClick={e=>disposeButtonClick(e, 'onCancel')}>{cancelText || 'Cancel'}</button>
                        </li>
                        <li className="nav-item">
                            <button className="action-primary" onClick={e=>disposeButtonClick(e, 'onConfirm')}>{confirmText||'Confirm'}</button>
                        </li>
                    </ul>
                </nav>
            </div>
        </div>
    )
}

window.LearningTribes = window.LearningTribes || {}
window.LearningTribes.Notification = {
    Warning: NotificationFactory('warning'),
    Error: NotificationFactory('error'),
    Info: NotificationFactory('info'),
}
