import React, { useState, useEffect, useCallback, useMemo } from 'react'
import Dropdown from 'lt-react-dropdown'


const useNumberLocaleFormatter = languageCode => useMemo(() => new Intl.NumberFormat(languageCode), [languageCode])

// for leader board page.
const Ranks = ({list, totalUser, lastUpdate, isLoading, languageCode}) => {
  const forceLastItemActive = (index) => {
    // const isForceActive = list.filter(p=>p.Active).length <= 0
    // return index == list.length - 1 && isForceActive ? true : false
    return false
  }
  const numberLocaleFormatter = useNumberLocaleFormatter(languageCode)

  return (
    <div className={'rank' + (isLoading ? ' loading' : '')}>
      <table>
        <thead>
          <tr>
            <th>{gettext('Position')}</th>
            <th>{gettext('Name')}</th>
            <th>{gettext('Points')}</th>
          </tr>
        </thead>
        <tbody>
          {list.map((item, index) => (
            <tr key={index} {...(item.Active || forceLastItemActive(index) ? {className: 'active'} : {})}>
              <td className={item.OrderStatus}>{`${item.Rank}`}</td>
              <td><img src={`${item.Portrait}`} alt="" /><b>{item.Name}</b><time>{item.DateStr}</time></td>
              <td><strong>{numberLocaleFormatter.format(item.Points)} {gettext('pt.')}</strong></td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="loading-block"><i className="fas fa-spinner fa-spin"></i></div>
      <div className="last-update">
        <i className="fa fa-user"></i>
        <small>{gettext('There are currently ${totalUser} learners. Last update: ${lastUpdate}.').replace('${totalUser}', totalUser).replace('${lastUpdate}', lastUpdate)}</small>
      </div>
    </div>
  )
}

const Missions = ({missionConfig, mission, downloadable}) => {
  return (
    <aside className="mission">
      <h2>{gettext('My Challenges')}</h2>
      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>{gettext('My Challenges')}</th>
              <th>{gettext('Points')}</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(missionConfig).map(([key, {message, times, icon = 'far fa-user'}]) => (
              <tr key={key}>
                <td>
                  <div className="mission__icon-wrapper"><i className={icon}></i></div>
                  <div className="mission__text-wrapper">
                    <div>{message}</div>
                    <small>{gettext('You have won ${value} point(s).').replace('${value}', mission[key] * times || 0)}</small>
                  </div>
                </td>
                <td>+{times}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {downloadable ?
          <>
          <div className="download-actions-wrapper">
            <button className="action-primary">
              <span className="button-text">{gettext('Download the ranking')}</span>
              <span className="button-icon">
                <i className="far fa-chevron-down"></i>
              </span>
            </button>
            <ul className="action-dropdown-list is-hidden">
              <li className="action-item">
                <a className="action-csv" data-format="csv" href="">CSV</a>
              </li>
              <li className="action-item">
                <a className="action-excel" data-format="xls" href="">Excel</a>
              </li>
            </ul>
          </div>
          <p className="export-info">{gettext('The export you are about to download will take into account the ranking selection you have made on the top of the leaderboard table.')}</p>
          <div className="dropdown-download-menu" data-endpoint="/analytics/list_table_downloads/leaderboard"></div>
          </>
          :
          null
      }
    </aside>
  )
}

export const LeaderBoard = ({missionConfig, lastUpdate, totalUser, mission, list, languageCode, downloadable}) => {
  const [state, setState] = useState({
    cacheObj: {},
    isLoading: true,
    lastUpdate,
    totalUser,
    mission,
    list,
  })
  const deriveState = state => setState(prevState => Object.assign(prevState, state))

  const fetchData = useCallback((period, top=50) => {
    const { cacheObj } = state
    deriveState({isLoading: true})

    if (!cacheObj[period]) {
      fetch(`/analytics/leaderboard/json/?period=${period}&top=${top}`)
        .then(res => res.json())
        .then(({list, mission, lastUpdate, totalUser}) => {
          setState(prevState => ({
            ...prevState,
            list,
            lastUpdate,
            mission,
            totalUser,
            isLoading: false,
            cacheObj: {
              ...prevState.cacheObj,
              [period]: {list, lastUpdate},
            }
          }))
        })
    } else {
      const {list, lastUpdate} = cacheObj[period]
      deriveState({
        list,
        lastUpdate,
        isLoading: false
      })
    }
  })

  useEffect(() => {
    fetchData('')
  }, [])

  const handlePeriodChange = useCallback((item) => {
    fetchData(item.value)
  })

  const periodOptions = [
    {text: gettext('All'), value: 'all'},
    {text: gettext('Week'), value: 'week'},
    {text: gettext('Month'), value: 'month'},
  ]

  return (
    <React.Fragment>
      <section className="banner">
        <section className="welcome-wrapper">
          <h2>{gettext('Leaderboard')}</h2>
        </section>
      </section>
      <section className="headline-lists">
        <section className="headline">
          <h2>{gettext('Leaderboard')}</h2>
          <div className="period">
            <span>{gettext('Ranking')}</span>
            <i>|</i>
            <Dropdown sign='caret' data={periodOptions} onChange={handlePeriodChange} />
          </div>

        </section>
        <section className="lists">
          <Ranks {...state} languageCode={languageCode} />
          <Missions missionConfig={missionConfig} mission={state.mission} downloadable={downloadable} />
        </section>
      </section>
    </React.Fragment>
  )
}

// for dashboard's leader side board
export const LeaderSideBoard = ({languageCode}) => {
  const [list, setList] = useState([])
  const fetchData = useCallback((period, top) =>
    fetch(`/analytics/leaderboard/json/?period=${period}&top=${top}`)
      .then(res => res.json())
      .then(({list}) => setList(list))
  )
  const numberLocaleFormatter = useNumberLocaleFormatter(languageCode)

  useEffect(() => {
    fetchData('', 5)
  }, [])

  return (
    <React.Fragment>
      <div className="title">
        <h3>{gettext('Leaderboard')}</h3>
        <a href="/analytics/leaderboard/">{gettext('Show more')} <i className="far fa-chevron-right"></i> </a>
      </div>
      <div className="board-content">
        <table>
          <thead>
            <tr>
              <th>{gettext('Position')}</th>
              <th>{gettext('Name')}</th>
              <th>{gettext('Points')}</th>
            </tr>
          </thead>
          <tbody>
            {list.map((item, index) => (
              <tr key={index}>
                <td><strong>{`${index + 1}.`}</strong></td>
                <td><img src={`${item.Portrait}`} alt="" /><span className="name">{item.Name}</span></td>
                <td><strong>{numberLocaleFormatter.format(item.Points)}</strong> <span>points</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </React.Fragment>
  )
}
