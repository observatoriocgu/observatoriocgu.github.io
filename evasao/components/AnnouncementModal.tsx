import React, { useState, useEffect } from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faTimes } from '@fortawesome/free-solid-svg-icons';

// Defina como true para reativar o popup de novidade
const ANNOUNCEMENT_ENABLED = false;

const AnnouncementModal: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (!ANNOUNCEMENT_ENABLED) return;
    // Apenas mostrar o modal na primeira vez que a página é carregada
    // Usar localStorage para rastrear se o usuário já viu o modal
    const alreadyShown = localStorage.getItem('announcementModalShown');
    if (!alreadyShown) {
      setIsOpen(true);
      localStorage.setItem('announcementModalShown', 'true');
    }
  }, []);

  const closeModal = () => {
    setIsOpen(false);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-gray-900 rounded-lg shadow-2xl max-w-md w-full mx-4 border border-gray-700 p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-2xl font-bold text-red-400">📢 Novidade</h2>
          <button
            onClick={closeModal}
            className="text-gray-400 hover:text-gray-200 transition-colors"
            aria-label="Fechar"
          >
            <FontAwesomeIcon icon={faTimes} size="lg" />
          </button>
        </div>

        <div className="space-y-4 text-gray-300">
          <p>
            O Observatório das Evasões agora rastreia também os Auditores da CGU aprovados em outros concursos que estão <span className="font-semibold text-amber-400">aguardando nomeação</span>.
          </p>

          <p>
            Se você tem informações sobre Auditores que já foram aprovados em outros concursos, <span className="font-semibold text-amber-400">entre em contato conosco</span>! Suas informações são importantes para manter este observatório atualizado.
          </p>

          <div className="bg-gray-800 rounded p-3 border-l-4 border-amber-500">
            <p className="text-sm">
              ⬇️ Scroll até o final da página para encontrar o <span className="font-semibold">formulário de colaboração</span>.
            </p>
          </div>
        </div>

        <button
          onClick={closeModal}
          className="w-full mt-6 px-4 py-2 bg-red-600 text-white font-bold rounded hover:bg-red-700 transition-colors focus:outline-none focus:ring-2 focus:ring-red-500"
        >
          Entendi
        </button>
      </div>
    </div>
  );
};

export default AnnouncementModal;
