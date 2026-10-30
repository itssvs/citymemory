// Plain-language privacy notice shown before a citizen reports a problem (English and Tamil).
import { ShieldCheck } from 'lucide-react'
import { usePrefs } from '../i18n'
import { NoticeList } from '../ui'

export default function PrivacyNotice({ checked, onChange }) {
  const { t } = usePrefs()
  return (
    <section className="privacy" aria-labelledby="privacy-title">
      <h3 id="privacy-title" className="privacy-title"><ShieldCheck size={16} aria-hidden="true" />{t('pn_title')}</h3>
      <NoticeList />
      <label className="consent">
        <input type="checkbox" required checked={checked} onChange={(e) => onChange(e.target.checked)} />
        <span>{t('pn_agree')}</span>
      </label>
    </section>
  )
}
