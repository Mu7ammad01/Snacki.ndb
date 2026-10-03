import type { Lang } from "./types";

export const CONTACT = {
  whatsapp: "22237939409", // +222 37 93 94 09
  whatsappDisplay: "37 93 94 09",
};

export const ZONES = [
  { id: "ndb", fr: "Nouadhibou (ville)", ar: "انواذيبو (المدينة)" },
  { id: "cansado", fr: "Cansado", ar: "كانصادو" },
  { id: "autre", fr: "Autre quartier", ar: "حي آخر" },
] as const;

export const PAYMENTS = [
  { id: "cash", fr: "Espèces", ar: "نقدًا" },
  { id: "bankily", fr: "Bankily", ar: "بنكيلي" },
  { id: "sedad", fr: "Sedad", ar: "السداد" },
  { id: "bimbank", fr: "Bimbank", ar: "بيم بنك" },
  { id: "bamis", fr: "Bamis Digital", ar: "باميس ديجيتال" },
] as const;

const fr = {
  introTitle: "Jus frais et délices, prêts en quelques minutes",
  introText: "À emporter ou livrés à Nouadhibou et Cansado.",
  s1: "1. Choisissez", s2: "2. Vos infos", s3: "3. Suivi en direct",
  all: "Tout", delices: "Délices", jus: "Jus naturels",
  top: "N°1 des ventes", pop: "Populaire",
  add: "Ajouter", less: "Retirer un", more: "Ajouter un",
  seeCart: "Voir mon panier",
  waLabel: "WhatsApp", cash: "Espèces",
  cartTitle: "Mon panier", infoTitle: "Vos informations", doneTitle: "Commande enregistrée",
  emptyCart: "Votre panier est vide.",
  estimate: "Total estimé",
  items: (n: number) => n + (n > 1 ? " articles" : " article"),
  next: "Continuer", validate: "Valider la commande", sending: "Envoi…",
  name: "Prénom", namePh: "Ex. Aicha", nameErr: "Indiquez votre prénom (2 à 40 lettres).",
  phone: "Téléphone", phoneErr: "Numéro à 8 chiffres, commençant par 2, 3 ou 4.",
  mode: "Comment récupérer ?", pickup: "À emporter", pickupSub: "au snack", delivery: "Livraison", deliverySub: "à domicile",
  zone: "Quartier", landmark: "Adresse ou repère", landmarkPh: "Ex. près de la mosquée, maison bleue",
  landmarkErr: "Indiquez un repère pour le livreur (3 à 100 caractères).",
  feeNote: "Les frais de livraison s’affichent dans le suivi dès que le snack accepte la commande.",
  payment: "Paiement", note: "Remarque (facultatif)", notePh: "Ex. moins sucré, sans lait…",
  orderNo: "Votre numéro de commande", total: "Total",
  track: "Suivre ma commande",
  sentToShop: "Votre commande est arrivée au snack. Suivez-la en direct : délai, frais de livraison et statut.",
  contactWa: "Une question ? Écrivez-nous sur WhatsApp",
  contactMsg: (n: string) => `Bonjour Snacki, à propos de ma commande ${n} :`,
  after: "Gardez cette page ouverte ou le lien de suivi : il reste valable 24 h.",
  newOrder: "Nouvelle commande",
  back: "Retour", close: "Fermer",
  errInvalid: "Commande refusée : vérifiez vos informations.",
  errUnavailable: "Un produit n'est plus disponible. Retirez-le du panier.",
  errRate: (s: number) => `Trop de commandes en peu de temps. Réessayez dans ${s} s.`,
  errNetwork: "Connexion impossible. Vérifiez votre réseau et réessayez.",
  menuDown: "Le menu est momentanément indisponible. Commandez directement sur WhatsApp au 37 93 94 09.",
  trackTitle: "Suivi de commande", trackLoading: "Chargement…",
  trackNotFound: "Commande introuvable ou lien expiré (24 h).",
  trackRefresh: "Mise à jour automatique toutes les 10 secondes.",
  readyAt: (h: string) => `Prête vers ${h}`, fee: "Livraison", articles: "Articles", toPay: "À payer", reason: "Motif",
  status: { recue: "Reçue", acceptee: "Acceptée", en_preparation: "En préparation", prete: "Prête", livree: "Livrée", refusee: "Refusée", annulee: "Annulée" },
  handedPickup: "Retirée",
  backToMenu: "Retour au menu",
};

type Dict = typeof fr;

const ar: Dict = {
  introTitle: "عصائر طازجة وحلويات، جاهزة في دقائق",
  introText: "للأخذ أو التوصيل في انواذيبو وكانصادو.",
  s1: "١. اختر", s2: "٢. معلوماتك", s3: "٣. تتبع مباشر",
  all: "الكل", delices: "حلويات", jus: "عصائر طبيعية",
  top: "الأكثر طلبًا", pop: "مطلوب",
  add: "أضف", less: "أنقص واحدًا", more: "زد واحدًا",
  seeCart: "عرض السلة",
  waLabel: "واتساب", cash: "نقدًا",
  cartTitle: "سلتي", infoTitle: "معلوماتك", doneTitle: "تم تسجيل الطلب",
  emptyCart: "سلتك فارغة.",
  estimate: "المجموع التقديري",
  items: (n: number) => n + " " + (n === 1 ? "منتج" : "منتجات"),
  next: "متابعة", validate: "تأكيد الطلب", sending: "جارٍ الإرسال…",
  name: "الاسم", namePh: "مثال: عائشة", nameErr: "أدخل اسمك (من 2 إلى 40 حرفًا).",
  phone: "الهاتف", phoneErr: "رقم من 8 أرقام يبدأ بـ 2 أو 3 أو 4.",
  mode: "كيف تستلم طلبك؟", pickup: "للأخذ", pickupSub: "من المحل", delivery: "توصيل", deliverySub: "إلى المنزل",
  zone: "الحي", landmark: "العنوان أو علامة مميزة", landmarkPh: "مثال: قرب المسجد، المنزل الأزرق",
  landmarkErr: "أدخل علامة مميزة لعامل التوصيل (من 3 إلى 100 حرف).",
  feeNote: "يظهر سعر التوصيل في صفحة التتبع بمجرد قبول المحل للطلب.",
  payment: "طريقة الدفع", note: "ملاحظة (اختياري)", notePh: "مثال: سكر أقل، بدون حليب…",
  orderNo: "رقم طلبك", total: "المجموع",
  track: "تتبع طلبي",
  sentToShop: "وصل طلبك إلى المحل. تابعه مباشرة: وقت التجهيز وسعر التوصيل والحالة.",
  contactWa: "لديك سؤال؟ راسلنا عبر واتساب",
  contactMsg: (n: string) => `مرحبًا Snacki، بخصوص طلبي ${n}:`,
  after: "احتفظ بهذه الصفحة أو برابط التتبع: يبقى صالحًا 24 ساعة.",
  newOrder: "طلب جديد",
  back: "رجوع", close: "إغلاق",
  errInvalid: "تم رفض الطلب: تحقق من معلوماتك.",
  errUnavailable: "أحد المنتجات لم يعد متوفرًا. احذفه من السلة.",
  errRate: (s: number) => `طلبات كثيرة في وقت قصير. أعد المحاولة بعد ${s} ثانية.`,
  errNetwork: "تعذّر الاتصال. تحقق من الشبكة وأعد المحاولة.",
  menuDown: "القائمة غير متاحة مؤقتًا. اطلب مباشرة عبر واتساب على 37939409.",
  trackTitle: "تتبع الطلب", trackLoading: "جارٍ التحميل…",
  trackNotFound: "الطلب غير موجود أو انتهت صلاحية الرابط (24 ساعة).",
  trackRefresh: "تحديث تلقائي كل 10 ثوانٍ.",
  readyAt: (h: string) => `جاهز حوالي ${h}`, fee: "التوصيل", articles: "المنتجات", toPay: "المبلغ المطلوب", reason: "السبب",
  status: { recue: "تم الاستلام", acceptee: "مقبول", en_preparation: "قيد التحضير", prete: "جاهز", livree: "تم التسليم", refusee: "مرفوض", annulee: "ملغى" },
  handedPickup: "تم الاستلام من المحل",
  backToMenu: "العودة إلى القائمة",
};

export const T: Record<Lang, Dict> = { fr, ar };

const fmtPlain = (n: number) => n.toLocaleString("fr-FR").replace(/[  ]/g, " ");
/** Nombre isolé du sens de lecture (évite l'inversion des blocs de chiffres en arabe). */
export const fmt = (n: number) => "⁦" + fmtPlain(n).replace(/ /g, " ") + "⁩";
export { fmtPlain };
