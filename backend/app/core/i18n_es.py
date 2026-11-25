"""
Espanhol das mensagens da API, indexado pelo texto em português.

Chaves com {0}, {1}… são trechos variáveis (f-strings e mensagens dinâmicas);
sem tradução, a mensagem sai em português.
"""
ES: dict[str, str] = {
    "Erro interno do servidor.":
        "Error interno del servidor.",
    "Telefone inválido. Use DDD + número.":
        "Teléfono inválido. Usa código de área + número.",
    "Informe ao menos telefone, e-mail ou @ do Instagram.":
        "Ingresa al menos teléfono, correo o @ de Instagram.",
    "Status inválido.":
        "Estado inválido.",
    "Já existe um lead com esse telefone ou e-mail: {0}.":
        "Ya existe un lead con ese teléfono o correo: {0}.",
    "Seus dados foram excluídos.":
        "Tus datos fueron eliminados.",
    "Sua solicitação foi recebida e será processada em até 30 dias.":
        "Tu solicitud fue recibida y se procesará en un plazo de 30 días.",
    "Código de confirmação não encontrado.":
        "No se encontró el código de confirmación.",
    "Conexão sem Phone Number ID.":
        "Conexión sin Phone Number ID.",
    "O horário final precisa ser depois do inicial.":
        "La hora final debe ser posterior a la inicial.",
    "Regra não encontrada.":
        "No se encontró la regla.",
    "Template não encontrado. Sincronize os templates e tente de novo.":
        "No se encontró la plantilla. Sincroniza las plantillas e inténtalo de nuevo.",
    "Só templates aprovados pela Meta podem ser usados no follow-up.":
        "Solo las plantillas aprobadas por Meta se pueden usar en el seguimiento.",
    "Esta chamada foi atendida por outra pessoa.":
        "Otra persona atendió esta llamada.",
    "Podemos te ligar pelo WhatsApp para continuar o atendimento?":
        "¿Podemos llamarte por WhatsApp para continuar la atención?",
    "Recurso indisponível.":
        "Función no disponible.",
    "WhatsApp não conectado.":
        "WhatsApp no conectado.",
    "Chamada não encontrada.":
        "No se encontró la llamada.",
    "Apenas admins podem alterar as ligações.":
        "Solo los administradores pueden cambiar las llamadas.",
    "Este lead não tem telefone de WhatsApp.":
        "Este lead no tiene teléfono de WhatsApp.",
    "O contato pediu para não ser contatado pelo WhatsApp (opt-out).":
        "El contacto pidió no ser contactado por WhatsApp (opt-out).",
    "Sem opt-in de WhatsApp: registre o consentimento do contato em Leads antes de ligar.":
        "Sin opt-in de WhatsApp: registra el consentimiento del contacto en Leads antes de llamar.",
    "Lead não encontrado.":
        "No se encontró el lead.",
    "Não foi possível ler as credenciais do WhatsApp. Reconecte o número.":
        "No se pudieron leer las credenciales de WhatsApp. Vuelve a conectar el número.",
    "Esta chamada não está mais disponível: outra pessoa atendeu ou ela terminou.":
        "Esta llamada ya no está disponible: otra persona atendió o terminó.",
    "Não foi possível falar com a Meta. Tente de novo.":
        "No se pudo comunicar con Meta. Inténtalo de nuevo.",
    "Limite de ligações para este contato atingido. Tente de novo mais tarde.":
        "Se alcanzó el límite de llamadas para este contacto. Inténtalo más tarde.",
    "O contato ainda não permitiu ligações. Peça a permissão: ele responde no próprio WhatsApp.":
        "El contacto todavía no permitió llamadas. Pide el permiso: responde en el propio WhatsApp.",
    "A Meta devolveu uma chamada inválida. Tente de novo.":
        "Meta devolvió una llamada inválida. Inténtalo de nuevo.",
    "O cliente não fala com você há mais de 24 horas. Nesse caso a Meta só aceita o pedido dentro de um template aprovado com o botão de ligação.":
        "El cliente no habla contigo hace más de 24 horas. En ese caso Meta solo acepta la solicitud dentro de una plantilla aprobada con el botón de llamada.",
    "Você já está em uma chamada.":
        "Ya estás en una llamada.",
    "O número não está registrado na Cloud API. Em Conexões Meta → WhatsApp, clique em Registrar número.":
        "El número no está registrado en la Cloud API. En Conexiones de Meta → WhatsApp, haz clic en Registrar número.",
    "O PIN não confere com o da verificação em duas etapas do número.":
        "El PIN no coincide con el de la verificación en dos pasos del número.",
    "O destinatário não está na lista de números de teste do app (modo desenvolvimento). Adicione-o no painel da Meta.":
        "El destinatario no está en la lista de números de prueba de la app (modo desarrollo). Agrégalo en el panel de Meta.",
    "Janela de 24h expirada — envie um template aprovado.":
        "Ventana de 24 h vencida — envía una plantilla aprobada.",
    "Template não encontrado ou não aprovado nesse idioma. Sincronize os templates.":
        "Plantilla no encontrada o no aprobada en ese idioma. Sincroniza las plantillas.",
    "Token da Meta expirado ou inválido. Reconecte em Conexões Meta.":
        "Token de Meta vencido o inválido. Vuelve a conectar en Conexiones de Meta.",
    "A conta do WhatsApp está sem forma de pagamento válida, e a Meta exige uma para as ligações.":
        "La cuenta de WhatsApp no tiene un método de pago válido, y Meta lo exige para las llamadas.",
    "Este número usa SIP, então as ligações não funcionam pela API.":
        "Este número usa SIP, así que las llamadas no funcionan por la API.",
    "O contato ainda não permitiu ligações deste número. Peça a permissão pelo WhatsApp antes de ligar.":
        "El contacto todavía no permitió llamadas de este número. Pide el permiso por WhatsApp antes de llamar.",
    "O número atingiu o limite diário de ligações da Meta. Tente de novo mais tarde.":
        "El número alcanzó el límite diario de llamadas de Meta. Inténtalo más tarde.",
    "As ligações não estão ativas neste número. Ative em Conexões Meta → WhatsApp.":
        "Las llamadas no están activas en este número. Actívalas en Conexiones de Meta → WhatsApp.",
    "O número atingiu o limite de chamadas simultâneas. Tente de novo em instantes.":
        "El número alcanzó el límite de llamadas simultáneas. Inténtalo de nuevo en unos instantes.",
    "A chamada não conectou. Verifique a rede e tente de novo.":
        "La llamada no se conectó. Revisa la red e inténtalo de nuevo.",
    "O áudio não conectou a tempo e a chamada foi encerrada.":
        "El audio no se conectó a tiempo y la llamada se terminó.",
    "A Meta pausou temporariamente as ligações deste número por baixa qualidade.":
        "Meta pausó temporalmente las llamadas de este número por baja calidad.",
    "A Meta só ativa ligações em contas com limite de 2.000 destinatários por dia ou mais.":
        "Meta solo activa las llamadas en cuentas con un límite de 2.000 destinatarios por día o más.",
    "O app ainda não está pronto para ligações: falta assinar o webhook de chamadas.":
        "La app todavía no está lista para llamadas: falta suscribir el webhook de llamadas.",
    "A Meta exige opt-in para mensagens iniciadas pela empresa. Sem ele, quem recebe tende a bloquear ou denunciar: a qualidade do número cai, o limite diário de envios diminui e a Meta pode restringir ou banir o número (às vezes a conta do WhatsApp Business inteira). Pela LGPD, a responsabilidade pelo contato sem consentimento é da empresa que envia.":
        "Meta exige opt-in para los mensajes iniciados por la empresa. Sin él, quien los recibe tiende a bloquear o denunciar: la calidad del número baja, el límite diario de envíos disminuye y Meta puede restringir o bloquear el número (a veces toda la cuenta de WhatsApp Business). Según la ley de protección de datos, la responsabilidad por contactar sin consentimiento es de la empresa que envía.",
    "A Meta recusou o envio: {0}":
        "Meta rechazó el envío: {0}",
    "Janela de 24h expirada — o cliente não responde há mais de 24 horas. Envie um template aprovado para reabrir a conversa.":
        "Ventana de 24 h vencida — el cliente no responde hace más de 24 horas. Envía una plantilla aprobada para reabrir la conversación.",
    "O Instagram só permite responder em até 24h após a última mensagem do cliente.":
        "Instagram solo permite responder hasta 24 h después del último mensaje del cliente.",
    "Este contato pediu para não receber mensagens (opt-out).":
        "Este contacto pidió no recibir mensajes (opt-out).",
    "Este contato não tem opt-in registrado para WhatsApp. ":
        "Este contacto no tiene opt-in registrado para WhatsApp. ",
    "O contato permitiu ligações por 7 dias.":
        "El contacto permitió llamadas por 7 días.",
    "O contato não permitiu ligações.":
        "El contacto no permitió llamadas.",
    "O contato permitiu ligações.":
        "El contacto permitió llamadas.",
    "Token inválido.":
        "Token inválido.",
    "Usuário não encontrado.":
        "No se encontró el usuario.",
    "Conta não encontrada.":
        "No se encontró la cuenta.",
    "Conta não encontrada":
        "No se encontró la cuenta",
    "Token inválido ou expirado.":
        "Token inválido o vencido.",
    "Acesso negado":
        "Acceso denegado",
    "Acesso restrito.":
        "Acceso restringido.",
    "Envie um arquivo PDF.":
        "Envía un archivo PDF.",
    "PDF excede o limite de 20 MB.":
        "El PDF supera el límite de 20 MB.",
    "Documento não encontrado.":
        "No se encontró el documento.",
    "O PDF original não está mais no servidor — envie o arquivo de novo.":
        "El PDF original ya no está en el servidor — vuelve a subir el archivo.",
    "Configure a API key da Gemini antes de ativar a IA.":
        "Configura la API key de Gemini antes de activar la IA.",
    "Conexão não encontrada.":
        "No se encontró la conexión.",
    "Plano inválido. Escolha 'autonomo' ou 'agencia'.":
        "Plan inválido. Elige 'autonomo' o 'agencia'.",
    "Nenhuma Página do Facebook encontrada. Crie uma Página primeiro.":
        "No se encontró ninguna Página de Facebook. Crea una Página primero.",
    "Nenhuma conta de anúncios encontrada para este usuário. Crie uma no Gerenciador de Anúncios da Meta primeiro.":
        "No se encontró ninguna cuenta publicitaria para este usuario. Crea una en el Administrador de anuncios de Meta primero.",
    "Token inválido ou conta já verificada.":
        "Token inválido o cuenta ya verificada.",
    "Username já em uso.":
        "El nombre de usuario ya está en uso.",
    "Credenciais inválidas.":
        "Credenciales inválidas.",
    "Conta desativada.":
        "Cuenta desactivada.",
    "Token de refresh inválido.":
        "Token de actualización inválido.",
    "Conta não encontrada. Efetue o checkout primeiro.":
        "No se encontró la cuenta. Completa el pago primero.",
    "Conta já ativada. Faça login.":
        "La cuenta ya está activada. Inicia sesión.",
    "Pagamento ainda não confirmado.":
        "El pago todavía no se confirmó.",
    "Apenas admins podem criar usuários.":
        "Solo los administradores pueden crear usuarios.",
    "Role inválida. Use 'admin' ou 'agent'.":
        "Función inválida. Usa 'admin' o 'agent'.",
    "Apenas admins podem alterar módulos.":
        "Solo los administradores pueden cambiar los módulos.",
    "Admin já tem acesso a todos os módulos.":
        "El administrador ya tiene acceso a todos los módulos.",
    "Apenas admins podem remover usuários.":
        "Solo los administradores pueden quitar usuarios.",
    "Você não pode remover a si mesmo.":
        "No puedes quitarte a ti mismo.",
    "Verifique seu email para ativar o acesso — enviamos o link de confirmação.":
        "Revisa tu correo para activar el acceso — te enviamos el enlace de confirmación.",
    "Automação não encontrada":
        "No se encontró la automatización",
    "Apenas contas do tipo Agência podem gerenciar clientes.":
        "Solo las cuentas de tipo Agencia pueden administrar clientes.",
    "Email do dono inválido.":
        "Correo del dueño inválido.",
    "Cliente não encontrado.":
        "No se encontró el cliente.",
    "Usuário do cliente não encontrado.":
        "No se encontró el usuario del cliente.",
    "Apenas admins podem gerenciar módulos.":
        "Solo los administradores pueden administrar módulos.",
    "Esta empresa não pertence à sua agência.":
        "Esta empresa no pertenece a tu agencia.",
    "Membro não encontrado neste tenant.":
        "No se encontró el miembro en esta cuenta.",
    "Apenas admins podem ver atribuições.":
        "Solo los administradores pueden ver las asignaciones.",
    "Apenas admins podem atribuir empresas.":
        "Solo los administradores pueden asignar empresas.",
    "Você não tem acesso a esta empresa. Peça ao admin para atribuí-la a você.":
        "No tienes acceso a esta empresa. Pide al administrador que te la asigne.",
    "Apenas admins podem iniciar conversas com template.":
        "Solo los administradores pueden iniciar conversaciones con plantilla.",
    "Conversa não encontrada.":
        "No se encontró la conversación.",
    "Instagram não conectado. Conecte-se primeiro.":
        "Instagram no conectado. Conéctalo primero.",
    "Instagram Business ID não encontrado. Informe o ig_user_id na requisição.":
        "No se encontró el Instagram Business ID. Indica el ig_user_id en la solicitud.",
    "Mídia não encontrada.":
        "No se encontró el archivo.",
    "A data de agendamento não pode estar no passado.":
        "La fecha de programación no puede estar en el pasado.",
    "Agendamento não encontrado.":
        "No se encontró la programación.",
    "Instagram não conectado.":
        "Instagram no conectado.",
    "ID da conta Instagram Business não configurado.":
        "El ID de la cuenta de Instagram Business no está configurado.",
    "Erro ao descriptografar token. Reconecte o Instagram.":
        "Error al descifrar el token. Vuelve a conectar Instagram.",
    "Formato não suportado. Use JPEG/PNG/WebP (imagem) ou MP4/MOV (vídeo).":
        "Formato no compatible. Usa JPEG/PNG/WebP (imagen) o MP4/MOV (video).",
    "Erro ao publicar. Tente novamente.":
        "Error al publicar. Inténtalo de nuevo.",
    "Erro ao listar mídias.":
        "Error al listar las publicaciones.",
    "Erro ao buscar dados do Instagram.":
        "Error al obtener los datos de Instagram.",
    "Erro ao buscar stories.":
        "Error al obtener las historias.",
    "Erro ao buscar perfil":
        "Error al obtener el perfil",
    "Apenas admins podem importar leads.":
        "Solo los administradores pueden importar leads.",
    "O CSV precisa de uma coluna de telefone (ex.: cabeçalho 'nome,telefone').":
        "El CSV necesita una columna de teléfono (ej.: encabezado 'nome,telefone').",
    "Lead não encontrado":
        "No se encontró el lead",
    "Não é possível mesclar um lead com ele mesmo.":
        "No se puede combinar un lead consigo mismo.",
    "Um ou ambos os leads não foram encontrados.":
        "No se encontró uno o ninguno de los leads.",
    "Nenhuma conta de anúncios conectada. Conecte pelo onboarding.":
        "Ninguna cuenta publicitaria conectada. Conéctala en el onboarding.",
    "Token de acesso inválido ou expirado.":
        "Token de acceso inválido o vencido.",
    "Conta de anúncios não configurada.":
        "Cuenta publicitaria no configurada.",
    "Nenhum campo para atualizar.":
        "No hay ningún campo para actualizar.",
    "Vídeo excede o limite de 300 MB.":
        "El video supera el límite de 300 MB.",
    "Nenhuma conta do Instagram vinculada a uma Página do Facebook nesta conta de anúncios.":
        "No hay ninguna cuenta de Instagram vinculada a una Página de Facebook en esta cuenta publicitaria.",
    "A mensagem do anúncio é obrigatória.":
        "El mensaje del anuncio es obligatorio.",
    "Página do Facebook não configurada nesta conexão de anúncios.":
        "Página de Facebook no configurada en esta conexión de anuncios.",
    "Para impulsionar um post, informe o link de destino.":
        "Para promocionar una publicación, indica el enlace de destino.",
    "Nenhuma conta do Instagram vinculada a uma Página do Facebook.":
        "No hay ninguna cuenta de Instagram vinculada a una Página de Facebook.",
    "Mensagem não encontrada.":
        "No se encontró el mensaje.",
    "Envio de mídia pelo Instagram ainda não é suportado — apenas texto.":
        "El envío de archivos por Instagram todavía no es compatible — solo texto.",
    "Plano não encontrado":
        "No se encontró el plan",
    "Use /auth/register para plano gratuito":
        "Usa /auth/register para el plan gratuito",
    "Email já cadastrado. Faça login.":
        "Correo ya registrado. Inicia sesión.",
    "Erro ao criar checkout":
        "Error al crear el pago",
    "Job não encontrado":
        "No se encontró la tarea",
    "Instagram Business ID não encontrado.":
        "No se encontró el Instagram Business ID.",
    "Erro ao analisar imagem":
        "Error al analizar la imagen",
    "Erro ao gerar vídeo":
        "Error al generar el video",
    "Erro ao descriptografar token.":
        "Error al descifrar el token.",
    "Erro ao publicar no Instagram.":
        "Error al publicar en Instagram.",
    "Requisição de verificação inválida.":
        "Solicitud de verificación inválida.",
    "Token de verificação inválido.":
        "Token de verificación inválido.",
    "Embedded Signup não configurado. Defina a variável WHATSAPP_CONFIG_ID no servidor (Meta App Dashboard > Login do Facebook para Empresas > Configurações).":
        "Embedded Signup no configurado. Define la variable WHATSAPP_CONFIG_ID en el servidor (Meta App Dashboard > Inicio de sesión con Facebook para empresas > Configuración).",
    "Apenas admins podem conectar o WhatsApp.":
        "Solo los administradores pueden conectar WhatsApp.",
    "Destinatário não identificado nesta conversa.":
        "No se identificó el destinatario en esta conversación.",
    "Mensagem sem wamid — não é possível reagir.":
        "Mensaje sin wamid — no es posible reaccionar.",
    "Apenas admins podem configurar credenciais.":
        "Solo los administradores pueden configurar credenciales.",
    "Apenas admins podem sincronizar templates.":
        "Solo los administradores pueden sincronizar plantillas.",
    "Apenas admins podem criar templates.":
        "Solo los administradores pueden crear plantillas.",
    "Apenas admins podem deletar templates.":
        "Solo los administradores pueden eliminar plantillas.",
    "Apenas admins podem disparar em massa.":
        "Solo los administradores pueden hacer envíos masivos.",
    "Conexão WhatsApp não configurada. Use PUT /whatsapp/credentials.":
        "La conexión de WhatsApp no está configurada. Conéctala en la página Conexiones de Meta.",
    "Informe de 1 a 3 botões.":
        "Indica de 1 a 3 botones.",
    "Lista exige button_text e ao menos uma seção.":
        "La lista requiere button_text y al menos una sección.",
    "Lista suporta no máximo 10 opções no total.":
        "La lista admite como máximo 10 opciones en total.",
    "Falha no upload para a Meta.":
        "Falló la subida a Meta.",
    "Falha ao enviar mensagem interativa.":
        "Error al enviar el mensaje interactivo.",
    "Falha ao enviar reação.":
        "Error al enviar la reacción.",
    "Falha no upload do vídeo.":
        "Falló la subida del video.",
    "Erro ao criar campanha":
        "Error al crear la campaña",
    "Erro ao atualizar campanha.":
        "Error al actualizar la campaña.",
    "Erro ao excluir campanha.":
        "Error al eliminar la campaña.",
    "Erro ao duplicar campanha.":
        "Error al duplicar la campaña.",
    "Erro ao criar conjunto":
        "Error al crear el conjunto",
    "Erro ao atualizar conjunto.":
        "Error al actualizar el conjunto.",
    "Erro ao excluir conjunto.":
        "Error al eliminar el conjunto.",
    "Erro ao duplicar conjunto.":
        "Error al duplicar el conjunto.",
    "Erro ao criar criativo":
        "Error al crear el creativo",
    "Erro ao criar criativo do post":
        "Error al crear el creativo de la publicación",
    "Página não encontrada entre as Páginas que você gerencia.":
        "No se encontró la Página entre las Páginas que administras.",
    "Selecione uma Página do Facebook primeiro.":
        "Selecciona primero una Página de Facebook.",
    "Erro ao inscrever a Página nos webhooks":
        "Error al suscribir la Página a los webhooks",
    "Erro ao cancelar a inscrição da Página":
        "Error al cancelar la suscripción de la Página",
    "Token expirado. Reconecte o Instagram.":
        "Token vencido. Vuelve a conectar Instagram.",
    "Erro ao comentar.":
        "Error al comentar.",
    "Erro ao responder.":
        "Error al responder.",
    "Erro ao atualizar o comentário.":
        "Error al actualizar el comentario.",
    "Erro ao excluir o comentário.":
        "Error al eliminar el comentario.",
    "Erro ao criar anúncio":
        "Error al crear el anuncio",
    "Erro ao atualizar anúncio.":
        "Error al actualizar el anuncio.",
    "Erro ao excluir anúncio.":
        "Error al eliminar el anuncio.",
    "Erro ao duplicar anúncio.":
        "Error al duplicar el anuncio.",
    "O módulo '{0}' não está disponível para o seu usuário. Fale com o administrador.":
        "El módulo '{0}' no está disponible para tu usuario. Habla con el administrador.",
    "Módulos inválidos: {0}":
        "Módulos inválidos: {0}",
    "Empresas inválidas: {0}":
        "Empresas inválidas: {0}",
    "Arquivo excede o limite de {0} MB para {1}.":
        "El archivo supera el límite de {0} MB para {1}.",
    "Arquivo excede o limite de {0} MB.":
        "El archivo supera el límite de {0} MB.",
    "Só é possível agendar até {0} dias à frente.":
        "Solo se puede programar hasta {0} días por adelantado.",
    "Erro ao enviar DM: {0}":
        "Error al enviar el DM: {0}",
    "Token expirado: {0}. Reconecte o Instagram.":
        "Token vencido: {0}. Vuelve a conectar Instagram.",
    "Token expirado: {0}":
        "Token vencido: {0}",
    "Erro ao publicar: {0}":
        "Error al publicar: {0}",
    "Dimensão inválida. Use: {0}":
        "Desglose inválido. Usa: {0}",
    "Mídia indisponível: {0}":
        "Archivo no disponible: {0}",
    "Período inválido. Use: {0}":
        "Período inválido. Usa: {0}",
}
