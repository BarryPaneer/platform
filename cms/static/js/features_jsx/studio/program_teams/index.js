
import React from 'react';
import {pick, template} from 'lodash'
import {Loading, ProgramBase} from "../shared"
import {MockedProgramAdmins} from '../../../../../../lms/static/js/mock_data/programAdmins'
import Prompt from '../../../../common/js/components/views/feedback_prompt'
import messages from '../../../../../../cms/static/js/views/message_of_users_and_roles'

/*
- texts translation
- add a switch to fit in development or production
* */
class NewMember extends React.Component {
    constructor(props, context) {
        super(props, context);
        this.state = {
            email:''
        }
    }
    render() {
        const {onCancel:onC,onSubmit:onS}=this.props
        return <div className="wrapper-create-element animate wrapper-create-user">
            <form className="form-create create-user" id="create-user-form" name="create-user-form">
                <div className="wrapper-form">
                    <h3 className="title">{gettext('Add a User to Your Learning Path Team')}</h3>
                    <fieldset className="form-fields">
                        <legend className="sr">{gettext('New Team Member Information')}</legend>

                        <ol className="list-input">
                            <li className="field text required create-user-email">
                                <label htmlFor="user-email-input">{gettext("User's Email Address")}</label>
                                <input onChange={e=>this.setState({email:e.currentTarget.value})} id="user-email-input" className="user-email-input" name="user-email" type="text"
                                       placeholder="example: username@domain.com" defaultValue={''}/>
                                <span className="tip tip-stacked">{gettext('Provide the email address of the user you want to add as Staff')}</span>
                            </li>
                        </ol>
                    </fieldset>
                </div>

                <div className="actions">
                    <button onClick={e=>{onC && onC(e); e.preventDefault()}} className="action action-secondary action-cancel">{gettext('Cancel')}</button>
                    <button onClick={e=>{
                        onS && onS(e,pick(this.state,['email'])); e.preventDefault()
                    }} className="action action-primary" type="submit">{gettext('Add User')}</button>
                </div>
            </form>
        </div>
    }
}

class MemberList extends React.Component {
    render() {
        const {data, onChange:onC, onDelete:onD} = this.props, Roles={staff:'Staff', triboo_instructor:'instructor', instructor:'Admin'}
        const rowRender=row=>{
            let login_user_is_staff = false;
            const isAdmin = row.role == 'instructor'?true:false;
            let isHideActions=row.role == 'instructor'
                && data.filter(p=>p.role=='instructor').length<2 ? true : false;
            const login_user = data.filter(p=>p.user.username==this.props.currentUserName)[0];

            if (login_user === undefined && (this.props.currentUserRole === "super_admin" || this.props.currentUserRole === "platform_admin")) {
                login_user_is_staff = false;
                isHideActions = false;
            } else {
                login_user_is_staff = login_user.role == 'staff';
                if (login_user_is_staff && login_user.is_studio_admin) {
                    isHideActions = true;
                }
            }

            return <li key={row.user.email} className="user-item" data-email="staff@example.com">

                <div className="item-metadata">
                <h3 className="user-name">
                  <span className="user-username">{row.user.username}</span>
                  <span className="user-email">
                    <a className="action action-email" href="mailto:staff@example.com" title="send an email message to staff@example.com">
                        {row.user.email}
                    </a>
                  </span>
                </h3>
                </div>

                <span className="wrapper-ui-badge">
                <span className={`flag flag-role flag-role-${row.role} is-hanging`}>
                  <span className="label sr">Current Role:</span>
                  <span className="value">
                      {gettext(Roles[row.role])}
                      {this.props.currentUserName == row.user.username && <span className="msg-you">You!</span>}
                  </span>
                </span>
                </span>

                <ul className="item-actions user-actions">
                    {row.role != 'triboo_instructor' &&
                        <li onClick={e=>{
                            e.currentTarget.querySelector('a') != null && onC && onC(e, isAdmin, row);
                            e.stopPropagation()
                        }} className={`action action-role`}>
                            {isHideActions
                                ? (data.filter(p=>p.role=='instructor').length<2 && row.role == 'instructor' && login_user_is_staff == false) ? <span className="admin-role notoggleforyou">{gettext('Promote another member to Admin to remove your admin rights')}</span> : ''
                                : <a href="#" className={`make-instructor admin-role ${isAdmin?'remove':'add'}-admin-role`}>
                                    <i className={`far fa-${isAdmin?'minus-circle':'crown'}`}></i>
                                    {row.role == 'instructor'? gettext('Remove admin access'): gettext('Add admin access')}
                                </a>
                            }

                        </li>
                    }
                    <li onClick={e=>{
                        onD && onD(e, row);
                        e.stopPropagation()
                    }} className={`action action-delete aria-disabled=`}>
                        <a href="#" className={`delete remove-user action-icon ${isHideActions?'is-disabled':''}`} data-id="staff@example.com">
                            <span className="icon far fa-trash-alt" aria-hidden="true"></span>
                            <span className="sr">Delete the user, staff</span>
                        </a>
                    </li>
                </ul>
            </li>
        }
        return <div className="user-list-wrapper">
            <div className="header"><span className="name">{gettext('Name')}</span><span className="action">{gettext('Action')}</span></div>
            <ol className="user-list" id="user-list">{data.map(p=>rowRender(p))}</ol>
          </div>
    }
}

class PageHeader extends React.Component {
    render() {

        const rowRender = (obj)=>{
            const {onClick, text, st}=obj
            const data = st.list;
            if (data.length > 0) {
                const currentUserName = st.userInfo.username;
                const currentRole = data.filter(p => p.user.username == currentUserName)[0];

                if (currentRole != undefined) {
                    const isHideButton = currentRole.role == 'staff' && currentRole.is_studio_admin;

                    if (isHideButton) {
                        return '';
                    }
                } else if (st.userInfo.admin_type != "super_admin" && st.userInfo.admin_type != "platform_admin") {
                    return '';
                }

            }

            return <li key={text} className="nav-item">
                        <a href="#" onClick={e=>onClick && onClick(e)} className={`button ${obj.className || ''}`}>
                            <span className={`icon far fa-${obj.icon}`} aria-hidden="true"></span>
                            {text}</a>
                    </li>
        }
        return <div className="wrapper-mast wrapper">
            <header className="mast has-actions has-subtitle">
                <h1 className="page-header">
                    <small className="subtitle">{gettext('Settings')}</small>
                    <span className="sr">&gt; </span>{gettext('Learning Path Team')}
                </h1>

                <nav className="nav-actions" aria-label="Page Actions">
                    <h3 className="sr">Page Actions</h3>
                    <ul>{this.props.actions.map(action=>rowRender(action))}</ul>
                </nav>
            </header>
        </div>
    }
}

const RoleType = {
    staff:'staff',
    instructor:'instructor',
    triboo_instructor:'triboo_instructor'
}

const MetaType = {
    post:{
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
    },
    delete:{
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json',
        },
    }
}

class ProgramTeam extends ProgramBase {
    constructor(props, context) {
        super(props, context);
        this.state = {
            list:[],
            isAdding:false
        }
    }

    async componentDidMount() {
        document.querySelector('body').classList.add('view-program-team')
        var [list, userInfo] = await Promise.all([
            this.fetchData(), this.fetchInfoOfLoginedUser()
        ])
        this.setState({
            list, userInfo
        })
        this.fetchDataAndSetList()
    }

    fetchInfoOfLoginedUser(){
        if (this.props.isDebug) {
            return new Promise(resolve=>{
                resolve({
                    username:'edx'
                })
            })
        }

        const url = '/api/user/v1/me'
        return fetch(url).then(res=>res.ok?res.json():{username:''})
            .then(json=>json)
            .catch(err => console.log(err))
    }
    fetchData(){
        if (this.props.isDebug) return new Promise(resolve =>resolve(MockedProgramAdmins))

        const url = `/api/team/v0/programadmins/${this.props.uuid}/`
        return fetch(url)
            .then(res=>res.ok?res.json():{results:[]})
            .then(json=>json.results) //this.setState({list:json.results})
            .catch(err=>console.log(err))
    }
    fetchDataAndSetList(extraParameters){
        this.fetchData().then(list=>this.setState({list, ...extraParameters}))
    }
    addAdminAccess(row){
        const t=gettext, realUrl = `/api/team/v0/programadmins/${this.props.uuid}/roles/`, mockUrl = '/program_team'
        fetch(this.props.isDebug?mockUrl:realUrl, {
            ...MetaType.post,
            body: JSON.stringify({
                role_name:RoleType.instructor,
                email:row.user.email
            })
        }).then(res=>{
            if (res.ok) {
                this.fetchDataAndSetList()
            }else{
                LearningTribes.Notification.Error({
                    title:gettext('Error'),
                    message:gettext('can\'t add admin access for this user')
                })
            }
            return res.json()
        }).then(()=>{
            //{"program_uuid":"19f92154-c1ff-4615-a232-f7b37854193e"}
        }).catch(err=>{
            LearningTribes.Notification.Error({
                title:gettext('Error'),
                message:gettext(err.message)
            })
        })
    }
    removeAdminAccess(row) {
        const realUrl = `/api/team/v0/programadmins/${this.props.uuid}/roles/`, mockUrl = '/program_team'
        fetch(this.props.isDebug?mockUrl:realUrl, {
            ...MetaType.delete,
            body: JSON.stringify({
                role_name:RoleType.staff,
                email:row.user.email
            })
        })
        .then(res=>{
            if (res.ok) {
                this.fetchDataAndSetList()
            }else{
                LearningTribes.Notification.Error({
                    title:gettext('Error'),
                    message:gettext('can\'t remove admin access from this user')
                })
            }
            return res.json()
        })
        .then(()=>{
            //{"program_uuid":"19f92154-c1ff-4615-a232-f7b37854193e"}
        }).catch(err=>{
            LearningTribes.Notification.Error({
                title:gettext('Error'),
                message:gettext(err.message)
            })
        })
    }
    deleteMember(row){
        const startDelete = (row)=>{
            const realUrl = `/api/team/v0/programadmins/${this.props.uuid}/`, mockUrl = '/program_team'
            fetch(this.props.isDebug?mockUrl:realUrl, {
                ...MetaType.delete,
                body: JSON.stringify({
                    email:row.user.email
                })
            })
                .then(res=>{
                    if (res.ok) {
                        this.fetchDataAndSetList()
                    }else{
                        LearningTribes.Notification.Error({
                            title:gettext('Error'),
                            message:gettext('can\'t remove this team member')
                        })
                    }
                    return res.json()
                })
                .then(data=>console.log(data))
            .catch(err=>{
                LearningTribes.Notification.Error({
                    title:gettext('Error'),
                    message:gettext(err.message)
                })
            })
        }
        let msg = new Prompt.Warning({
            title: messages.deleteUser.title,
            message:template(
                messages.deleteUser.messageTpl,
                {interpolate: /\{(.+?)}/g})(
                {email: row.user?.email || 'default@example.com', container: this.programData?.title || 'default program'}
            ),
            actions: {
                primary: {
                    text: messages.deleteUser.primaryAction,
                    click: (view)=> {
                        view.hide();
                        startDelete(row);
                        /*
                        // Use the REST API to delete the user:
                        self.changeRole(email, null, {errMessage: self.messages.errors.deleteUser});*/
                    }
                },
                secondary: {
                    text: messages.deleteUser.secondaryAction,
                    click: (view)=> { view.hide(); }
                }
            }
        });
        msg.show();


    }
    addMember(e,{email}){
        e.stopPropagation()
        const realUrl = `/api/team/v0/programadmins/${this.props.uuid}/roles/`, mockUrl = '/program_team'
        fetch(this.props.isDebug?mockUrl:realUrl, {
            ...MetaType.post,
            body: JSON.stringify({
                role_name:RoleType.staff,
                email
            })
        })
            .then(res=>{
                if (res.ok) {
                    this.fetchDataAndSetList({isAdding:false})
                }else{
                    LearningTribes.Notification.Error({
                        title:gettext('Error'),
                        message:gettext('can\'t add this user')
                    })
                }
                return res.json()
            })
            .then(data=>console.log(data))
    }

    getAside(){
        const t=gettext
        return <aside className="content-supplementary" role="complementary">
                  <div className="bit">
                      <h3 className="title-3">{t('Learning Path Team Roles')}</h3>
                      <p><i className="far fa-user-crown"></i><span><b>{t('Admin')}</b>{t('This user has Admin Access to the learning path, because they are the one who created the learning path or this user has been granted Admin Access by another Admin. They can add and remove other learning path team members. They have also the right to delete a learning path.')}</span>
                      </p>
                      <p><i className="far fa-user-edit"></i><span><b>{t('Staff')}</b>{t('This user can edit the learning path but cannot manage the learning path team (cannot add a new member or change other members’ access). They are co-authors.')}</span>
                      </p>
                      <p><i className="far"></i><span>{t('All learning path team members can access content in Studio and the LMS, but are not automatically enrolled in the learning path.')}</span>
                      </p>
                  </div>

                  <div className="bit show_transfer_ownership_hint">
                      <h3 className="title-3">{gettext('Transferring Ownership')}</h3>
                      <p dangerouslySetInnerHTML={{__html: gettext('Every program must have an Admin. If you are the Admin and you want to transfer ownership of the program, click {em_start}Add admin access{em_end} to make another user the Admin, then ask that user to remove you from the Learning Path Team list.').replace("{em_start}", "<strong>").replace("{em_end}", "</strong>")}}></p>
                  </div>
              </aside>
    }
    render() {
        const actions = [
                {
                    text:gettext('New Team Member'),
                    icon:'plus',
                    className:'new-button create-user-button',
                    onClick:()=>this.setState({isAdding:true}),
                    st: this.state
                }
            ]
        const t=gettext
        //const {query, selectedLanguages} = this.state
        return <div className={'program-team'}>
            <PageHeader actions={actions}/>
            <div className="wrapper-content wrapper">
              <section className="content">
                <article className="content-primary" role="main">
                    {this.state.isAdding && <NewMember onCancel={()=>this.setState({isAdding:false})}
                                                       onSubmit={this.addMember.bind(this)}
                    />}
                    <MemberList data={this.state.list} currentUserName={(this.state.userInfo || {}).username} currentUserRole={(this.state.userInfo || {}).admin_type}
                                onChange={(e, isAdmin, row)=>{
                                    /*console.log(isAdmin)
                                    console.log(row)*/
                                    !isAdmin?this.addAdminAccess(row):this.removeAdminAccess(row)

                                }}
                                onDelete={(e, row)=>this.deleteMember(row)}
                    />

                </article>
                  {this.getAside()}
              </section>
            </div>
        </div>
    }
}

class Menu extends React.Component{

    render() {
        const {menus,onBeforeClick} = this.props, menuRender=(menu)=>{
            return <li key={menu.text} className="nav-item">
                        <a href="#" onClick={e=>{
                            onBeforeClick && onBeforeClick(e,menu)
                            menu.onClick && menu.onClick(e, menu)
                        }}>{gettext(menu.text)}</a>
                    </li>
        }
        return <ol>
                <li className="nav-item nav-course-courseware">
                    <h3 className="title"><span className="label"><span className="label-prefix sr">Course </span><span
                        className="icon far fa-cogs" aria-hidden="true"></span>{gettext('Settings')}</span></h3>

                    <div className="wrapper wrapper-nav-sub">
                        <div className="nav-sub">
                            <ul>{menus.map(menu=>{ return menuRender(menu) })}</ul>
                        </div>
                    </div>
                </li>

            </ol>
    }
}

export {ProgramTeam, Menu}
