import React from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faEnvelope, faPaperPlane } from '@fortawesome/free-solid-svg-icons';

const CollaborationForm: React.FC = () => {
  return (
    <div className="mt-8 mb-8 rounded-xl p-6 bg-gray-900 border border-gray-800 shadow-2xl">
      <div className="text-center mb-6">
        <FontAwesomeIcon icon={faEnvelope} className="text-red-500 text-2xl mb-3" />
        <h3 className="text-xl font-semibold text-red-300 mb-2">
          Colabore com Informações
        </h3>
        <p className="text-gray-300 text-sm">
          Tem dados ou informações sobre evasão na CGU? Compartilhe conosco!
        </p>
        {/* Não exibir mensagens sobre anonimato; apenas não pedir nome */}
      </div>

      {/*
        Envio estático via FormSubmit (funciona no GitHub Pages)
        Primeira submissão pedirá verificação do email observatoriocgu@gmail.com.
      */}
      <form
        action="https://formsubmit.co/observatoriocgu@gmail.com"
        method="POST"
        className="space-y-4"
      >
        {/* Configurações do FormSubmit */}
        <input type="hidden" name="_captcha" value="false" />
        <input type="hidden" name="_subject" value="[Observatório CGU] Nova colaboração" />
        {/* Campo honeypot anti-bot */}
        <input type="text" name="_honey" className="hidden" tabIndex={-1} autoComplete="off" />

        {/* Sem campos de identificação */}

        <div>
          <label htmlFor="subject" className="block text-sm font-medium text-gray-300 mb-1">
            Assunto *
          </label>
          <select
            id="subject"
            name="subject"
            required
            className="w-full px-3 py-2 rounded-lg border border-gray-700 bg-gray-800 text-gray-100 placeholder-gray-500 focus:ring-2 focus:ring-red-500 focus:border-red-500 transition-colors"
          >
            <option value="">Selecione um assunto</option>
            <option value="Informar dados de evasão">Informar dados de evasão</option>
            <option value="Correção de dados existentes">Correção de dados existentes</option>
            <option value="Sugestão para o observatório">Sugestão para o observatório</option>
            <option value="Outro">Outro assunto</option>
          </select>
        </div>

        <div>
          <label htmlFor="message" className="block text-sm font-medium text-gray-300 mb-1">
            Mensagem *
          </label>
          <textarea
            id="message"
            name="message"
            required
            rows={4}
            className="w-full px-3 py-2 rounded-lg border border-gray-700 bg-gray-800 text-gray-100 placeholder-gray-500 focus:ring-2 focus:ring-red-500 focus:border-red-500 transition-colors resize-y caret-red-500"
            placeholder="Descreva as informações que deseja compartilhar ou a mensagem que deseja enviar..."
          />
        </div>

        <div className="text-center">
          <button
            type="submit"
            className="inline-flex items-center px-6 py-3 text-base font-medium text-white bg-red-600 border border-transparent rounded-lg shadow-sm hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 focus:ring-offset-gray-900 transition-colors duration-200"
          >
            <FontAwesomeIcon icon={faPaperPlane} className="mr-2" />
            Enviar Mensagem
          </button>
        </div>

        <div className="text-center">
          <p className="text-xs text-gray-400">
            Suas informações serão tratadas com confidencialidade e utilizadas, após verificação, apenas para fins do observatório.
          </p>
        </div>
      </form>
    </div>
  );
};

export default CollaborationForm;