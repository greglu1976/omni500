SETTINGS_MACROS_CONTENT_FIVE = r"""% ============================================
% МАКРОС ДЛЯ 5 СТОЛБЦОВ (с жесткой шапкой)
% ============================================
\newcommand{\startTable}[2]{%
    \footnotesize
    \begin{longtable}{|>{\centering\arraybackslash}m{3.8cm}|>{\centering\arraybackslash}m{3.3cm}|>{\centering\arraybackslash}m{2.7cm}|>{\centering\arraybackslash}m{2.8cm}|>{\centering\arraybackslash}m{3.0cm}|}
    \caption{#1\hfill\vspace{-0.5\baselineskip}}\label{#2}\\
    \hline
    \rowcolor{gray!20}
    Наименование уставки & Значение/Диапазон & Единица измерения & Шаг & Значение по умолчанию \\
    \hline
    \endfirsthead
    %
    \caption*{\hspace{3pt}\emph{Продолжение таблицы \ref{#2}\hfill\vspace{-0.5\baselineskip}}} \\
    \hline
    \rowcolor{gray!20}
    Наименование уставки & Значение/Диапазон & Единица измерения & Шаг & Значение по умолчанию \\
    \hline
    \endhead
}

% ============================================
% ОБЩИЙ МАКРОС ДЛЯ ЗАКРЫТИЯ
% ============================================
\newcommand{\stopTable}{%
    \end{longtable}%
    \normalsize
}
"""

SETTINGS_MACROS_CONTENT_SIX = r"""% ============================================
% МАКРОС ДЛЯ 6 СТОЛБЦОВ
% ============================================
\newcommand{\startTable}[3]{%
    \footnotesize
    \begin{longtable}{|>{\centering\arraybackslash}m{4.0cm}|>{\centering\arraybackslash}m{3.0cm}|>{\centering\arraybackslash}m{3.0cm}|>{\centering\arraybackslash}m{2.0cm}|>{\centering\arraybackslash}m{2.0cm}|>{\centering\arraybackslash}m{1.5cm}|}
    \caption{#1\hfill\vspace{-0.5\baselineskip}}\label{#2}\\
    \hline
    \rowcolor{gray!20}
    #3 \\
    \hline
    \endfirsthead
    %
    \caption*{\hspace{3pt}\emph{Продолжение таблицы \ref{#2}\hfill\vspace{-0.5\baselineskip}}} \\
    \hline
    \rowcolor{gray!20}
    #3 \\
    \hline
    \endhead
}

% ============================================
% ОБЩИЙ МАКРОС ДЛЯ ЗАКРЫТИЯ
% ============================================
\newcommand{\stopLongTable}{%
    \end{longtable}%
    \normalsize
}
"""