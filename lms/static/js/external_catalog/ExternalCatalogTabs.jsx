import React from 'react'


export default function CatalogTabs ({external_catalogs, current}) {
    const [platform, setPlatform] = React.useState(document.body.offsetWidth > 768 ? 'desktop' : 'mobile')
    React.useEffect(() => {
        const handleResize = () => {
            if (document.body.offsetWidth > 768) setPlatform('desktop')
            else setPlatform('mobile')
        }

        window.addEventListener('resize', handleResize)
        handleResize()

        return () => {
            window.removeEventListener('resize', handleResize)
        }
    }, [])

    if (external_catalogs.length < 2) return null

    return (
        <InnerCatalogTabs
            displayCount={platform === 'mobile' ? 2 : 4}
            external_catalogs={external_catalogs}
            current={current}
        />
    )
}

function InnerCatalogTabs ({external_catalogs, current, displayCount = 2}) {
    return (
        <div className="category_tabs">
            <a href="/all_external_catalog" className={'All' == current ? "current_category" : "categories"}>
                <span>{gettext("All")}</span>
            </a>
            {external_catalogs.slice(0, displayCount).map(item => (
                <a key={item.name} href={item.to} className={item.name == current ? "current_category" : "categories"}>
                    <span>{item.title}</span>
                </a>
            ))}
            {!!(external_catalogs.length > displayCount) && (
                <a href="javascript:void(0);" className="categories dropdown-chevron">
                    <span><i className="fas fa-chevron-double-right"></i></span>
                    <div className="dropdown-menu">
                        {external_catalogs.slice(displayCount, external_catalogs.length).map(item => (
                            <a key={item.name} href={item.to} className={`dropdown-item ${item.name == current ? "current" : ""}`}>
                                <span>{item.title}</span>
                            </a>
                        ))}
                    </div>
                </a>
            )}
        </div>
    )
}
