# ngx_valuation/services.py
import os
import google.generativeai as genai
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class ValuationService:
    """
    Service layer for financial analysis and AI-driven commentary.
    Contains business logic for the NGX Fundamental Analysis project.
    """

    @staticmethod
    def _parse_fin(value):
        """
        Internal utility to handle nullable fields and 'dirty' data.
        Ensures that None, empty strings, or strings like 'None'
        safely default to Decimal('0').
        """
        if value is None:
            return Decimal('0')

        clean_val = str(value).strip().replace(',', '')

        if not clean_val or clean_val.lower() in ['none', 'null', 'nan', '-']:
            return Decimal('0')

        try:
            return Decimal(clean_val)
        except (InvalidOperation, TypeError):
            return Decimal('0')

    @staticmethod
    def calculate_momentum_metrics(analysis_obj, is_wealth_creator=False, is_undervalued=False):
        """
        Layer 2: Price Action, Technical Momentum & Value-Momentum Matrix Engine.
        Handles optional inputs gracefully (defaults to 0 or None if omitted).
        """
        d = analysis_obj
        current_sp = Decimal(str(d.current_sp or '0'))
        hi_52 = ValuationService._parse_fin(d.fifty_two_week_high)
        lo_52 = ValuationService._parse_fin(d.fifty_two_week_low)
        sma_50 = ValuationService._parse_fin(d.sma_50)
        sma_200 = ValuationService._parse_fin(d.sma_200)

        # 1. 52-Week Range Positioning (% from 0% [At Low] to 100% [At High])
        range_span = hi_52 - lo_52
        if hi_52 > 0 and lo_52 > 0 and range_span > 0 and current_sp > 0:
            range_pos_pct = ((current_sp - lo_52) /
                             range_span) * Decimal('100')
            dist_from_high = ((hi_52 - current_sp) / hi_52) * Decimal('100')
            dist_from_low = ((current_sp - lo_52) / lo_52) * Decimal('100')
            has_52w_data = True
        else:
            range_pos_pct = Decimal('0')
            dist_from_high = Decimal('0')
            dist_from_low = Decimal('0')
            has_52w_data = False

        # 2. Moving Average Trend Signals
        has_sma_data = (sma_50 > 0 and sma_200 > 0 and current_sp > 0)
        above_sma_50 = current_sp > sma_50 if sma_50 > 0 else False
        above_sma_200 = current_sp > sma_200 if sma_200 > 0 else False
        golden_cross = sma_50 > sma_200 if (
            sma_50 > 0 and sma_200 > 0) else False

        # 3. Value-Momentum Matrix Classification
        if is_wealth_creator and is_undervalued:
            if has_52w_data and range_pos_pct <= Decimal('30'):
                matrix_status = "Deep Value Rebound Candidate"
                matrix_badge = "emerald"
                matrix_desc = "High operational quality trading near 52-week lows. Prime asymmetric entry zone."
            elif has_sma_data and above_sma_50 and golden_cross:
                matrix_status = "Quality Compounder in Uptrend"
                matrix_badge = "indigo"
                matrix_desc = "Fundamentals and technical momentum aligned in bullish trend."
            else:
                matrix_status = "Undervalued Quality Asset"
                matrix_badge = "emerald"
                matrix_desc = "Strong fundamentals available below fair forward valuation threshold."
        elif not is_wealth_creator:
            if has_52w_data and range_pos_pct <= Decimal('20'):
                matrix_status = "Value Trap / Falling Knife Warning"
                matrix_badge = "rose"
                matrix_desc = "Low/negative real return on capital. Low price reflects operational erosion."
            else:
                matrix_status = "Sub-Par Operational Performer"
                matrix_badge = "amber"
                matrix_desc = "Fails real return hurdle rate. Exercise caution despite price action."
        else:
            matrix_status = "Fairly Valued / Neutral Momentum"
            matrix_badge = "slate"
            matrix_desc = "Operational creator trading within expected market valuation range."

        return {
            "has_52w_data": has_52w_data,
            "has_sma_data": has_sma_data,
            "hi_52": hi_52.quantize(Decimal('0.01'), ROUND_HALF_UP),
            "lo_52": lo_52.quantize(Decimal('0.01'), ROUND_HALF_UP),
            "sma_50": sma_50.quantize(Decimal('0.01'), ROUND_HALF_UP),
            "sma_200": sma_200.quantize(Decimal('0.01'), ROUND_HALF_UP),
            "range_pos_pct": range_pos_pct.quantize(Decimal('0.01'), ROUND_HALF_UP),
            "dist_from_high": dist_from_high.quantize(Decimal('0.01'), ROUND_HALF_UP),
            "dist_from_low": dist_from_low.quantize(Decimal('0.01'), ROUND_HALF_UP),
            "above_sma_50": above_sma_50,
            "above_sma_200": above_sma_200,
            "golden_cross": golden_cross,
            "matrix_status": matrix_status,
            "matrix_badge": matrix_badge,
            "matrix_desc": matrix_desc
        }

    @staticmethod
    def calculate_layer1_metrics(analysis_obj):
        d = analysis_obj

        # Core Inputs
        sector = str(d.sector or 'NON_BANK').upper()
        op_profit = Decimal(str(d.operating_profit))
        finance_income = ValuationService._parse_fin(d.finance_income)
        one_off_gains = ValuationService._parse_fin(d.one_off_gains)
        tax_expenses = Decimal(str(d.tax_expenses))
        current_sp = Decimal(str(d.current_sp))
        total_os = Decimal(str(d.total_os))
        quarter = d.report_quarter
        pat = Decimal(str(d.profit_after_tax))
        total_equity = Decimal(str(d.total_equity))
        total_div = ValuationService._parse_fin(d.total_div)
        inf_input = Decimal(str(d.current_inf))
        inflation_rate = inf_input / Decimal('100')

        # Branching Logic based on Sector
        is_bank = sector == 'BANK'

        if is_bank:
            # --- BANKING METRICS ---
            roe = pat / total_equity if total_equity > 0 else Decimal('0')
            real_roe = roe - inflation_rate

            opex = ValuationService._parse_fin(d.finance_cost)
            cost_to_income = opex / \
                op_profit if op_profit > 0 else Decimal('0')

            nopat = Decimal('0')
            roic = Decimal('0')
            real_roic = Decimal('0')
            fcf = Decimal('0')
            fcf_conversion = Decimal('0')
        else:
            # --- NON-BANK INDUSTRIAL METRICS ---
            adj_ebit = op_profit + finance_income - one_off_gains
            nopat = adj_ebit - tax_expenses

            finance_cost = ValuationService._parse_fin(d.finance_cost)
            total_debt = ValuationService._parse_fin(d.total_debt)

            # Automated FCF Calculation: Net Operating Cash Flow - Capex (PPE)
            ocf = ValuationService._parse_fin(
                getattr(d, 'net_operating_cash_flow', 0))
            capex = ValuationService._parse_fin(getattr(d, 'capex_ppe', 0))
            fcf = ocf - capex

            invested_capital = total_equity + total_debt
            roic = (pat + finance_cost) / \
                invested_capital if invested_capital > 0 else Decimal('0')
            real_roic = roic - inflation_rate

            fcf_conversion = fcf / pat if pat != 0 else Decimal('0')
            roe = Decimal('0')
            real_roe = Decimal('0')
            cost_to_income = Decimal('0')

        # Common Shareholder Yield & Market Cap Calculations
        total_div_full = total_div * Decimal('1000')
        market_cap = total_os * current_sp
        payout_ratio = total_div / pat if pat > 0 else Decimal('0')
        div_yield = total_div_full / \
            market_cap if market_cap > 0 else Decimal('0')

        # Forward Valuation Projector Engine
        pat_full_units = pat * Decimal('1000')
        interim_eps = pat_full_units / \
            total_os if total_os > 0 else Decimal('0')

        multipliers = {
            'Q1': Decimal('4'),
            'Q2': Decimal('2'),
            'Q3': Decimal('1.333333'),
            'FY': Decimal('1')
        }
        multiplier = multipliers.get(quarter, Decimal('1'))

        forward_eps = interim_eps * multiplier
        forward_pe = current_sp / \
            forward_eps if forward_eps > 0 else Decimal('0')

        # Evaluate Flags for Momentum Matrix
        is_wealth_creator = (real_roe > 0) if is_bank else (real_roic > 0)
        is_undervalued = Decimal('0') < forward_pe <= (
            Decimal('5.00') if is_bank else Decimal('10.00'))

        # Calculate Layer 2 Technical Momentum & Price Action Metrics
        momentum_data = ValuationService.calculate_momentum_metrics(
            analysis_obj,
            is_wealth_creator=is_wealth_creator,
            is_undervalued=is_undervalued
        )

        return {
            "raw": {
                "sector": sector,
                "is_bank": is_bank,
                "nopat": nopat.quantize(Decimal('1'), ROUND_HALF_UP),
                "fcf": fcf.quantize(Decimal('1'), ROUND_HALF_UP),
                "roic": (roic * 100).quantize(Decimal('0.01'), ROUND_HALF_UP),
                "real_roic": (real_roic * 100).quantize(Decimal('0.01'), ROUND_HALF_UP),
                "roe": (roe * 100).quantize(Decimal('0.01'), ROUND_HALF_UP),
                "real_roe": (real_roe * 100).quantize(Decimal('0.01'), ROUND_HALF_UP),
                "cost_to_income": (cost_to_income * 100).quantize(Decimal('0.01'), ROUND_HALF_UP),
                "fcf_conv": (fcf_conversion * 100).quantize(Decimal('0.01'), ROUND_HALF_UP),
                "payout": (payout_ratio * 100).quantize(Decimal('0.01'), ROUND_HALF_UP),
                "div_yield": (div_yield * 100).quantize(Decimal('0.01'), ROUND_HALF_UP),
                "inflation_used": inf_input,
                "current_sp": current_sp.quantize(Decimal('0.01'), ROUND_HALF_UP),
                "interim_eps": interim_eps.quantize(Decimal('0.01'), ROUND_HALF_UP),
                "forward_eps": forward_eps.quantize(Decimal('0.01'), ROUND_HALF_UP),
                "forward_pe": forward_pe.quantize(Decimal('0.02'), ROUND_HALF_UP),
                "period_analyzed": quarter,
            },
            "momentum": momentum_data,
            "flags": {
                "is_efficient": (roe >= Decimal('0.18')) if is_bank else (roic >= Decimal('0.20')),
                "is_cash_backed": True if is_bank else (fcf_conversion >= Decimal('0.70')),
                "is_wealth_creator": is_wealth_creator,
                "healthy_payout": Decimal('0.30') <= payout_ratio <= Decimal('0.70'),
                "is_undervalued_pe": is_undervalued
            }
        }

    @staticmethod
    def get_ai_memo(ticker, metrics):
        """
        Fetches an AI-generated investment commentary based on calculated metrics.
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return "AI Commentary unavailable: Missing API Key."

        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name='gemini-flash-latest')

            raw = metrics['raw']
            mom = metrics.get('momentum', {})
            is_bank = raw['is_bank']

            # Dynamic prompt tailored to entity classification
            if is_bank:
                sector_metrics_prompt = f"""
            LAYER 1 BANKING OPERATIONAL METRICS:
            - Return on Equity (ROE): {raw['roe']}%
            - Real ROE: {raw['real_roe']}% (Hurdle Rate = Inflation: {raw['inflation_used']}%)
            - Cost-to-Income Ratio: {raw['cost_to_income']}%
            - Dividend Yield: {raw['div_yield']}%
            - Payout Ratio: {raw['payout']}%
            """
                rule_benchmark = "For commercial banks on the NGX, a Forward P/E at or below 5x represents a strong value benchmark."
            else:
                sector_metrics_prompt = f"""
            LAYER 1 INDUSTRIAL OPERATIONAL METRICS:
            - ROIC: {raw['roic']}%
            - Real ROIC: {raw['real_roic']}% (Hurdle Rate = Inflation: {raw['inflation_used']}%)
            - Free Cash Flow (Calculated): ₦{raw['fcf']} (in 000s)
            - FCF Conversion: {raw['fcf_conv']}%
            - Dividend Yield: {raw['div_yield']}%
            - Payout Ratio: {raw['payout']}%
            """
                rule_benchmark = "For non-banking stocks, a Forward P/E at or below 10x represents an asymmetric value entry point."

            momentum_prompt = f"""
            LAYER 2 TECHNICAL MOMENTUM & PRICE POSITIONING:
            - 52-Week Range: ₦{mom.get('lo_52', 0)} - ₦{mom.get('hi_52', 0)} (Position in Range: {mom.get('range_pos_pct', 0)}%)
            - Distance from 52W High: {mom.get('dist_from_high', 0)}% down
            - Moving Averages: SMA 50 = ₦{mom.get('sma_50', 0)}, SMA 200 = ₦{mom.get('sma_200', 0)}
            - Moving Average Signals: Above SMA 50 = {mom.get('above_sma_50')}, Above SMA 200 = {mom.get('above_sma_200')}, Golden Cross = {mom.get('golden_cross')}
            - Value-Momentum Matrix Classification: {mom.get('matrix_status', 'N/A')} ({mom.get('matrix_desc', '')})
            """

            prompt = f"""
            Act as a senior equity analyst specializing in the Nigerian Stock Exchange (NGX).
            Analyze {ticker} ({'Commercial Bank' if is_bank else 'Non-Banking / Industrial'}) using these operational metrics, market data, and forward projections:

            CORE MARKET & MACRO DATA:
            - Current Share Price: ₦{raw['current_sp']}
            - Headline Inflation Rate: {raw['inflation_used']}%

            {sector_metrics_prompt}

            FORWARD VALUATION ENGINE:
            - Financial Statement Period: {raw['period_analyzed']}
            - Calculated Interim Annualized EPS: ₦{raw['interim_eps']}
            - Projected Full-Year Forward EPS: ₦{raw['forward_eps']}
            - Calculated Forward P/E Ratio: {raw['forward_pe']}x

            {momentum_prompt}

            THEORETICAL FRAMEWORK TO APPLY (Forward Valuation & Value-Momentum Projector):
            "This projector states that equity markets fixate on past historical data, often missing massive inflection points in interim results. Forward valuation projects the true value of a stock based on future cash flows and annualized forward earnings. {rule_benchmark} Layer 2 Momentum evaluates whether price action presents a deep value entry opportunity or a falling knife."

            STRICT INSTRUCTIONS FOR THE ANALYSIS:
            1. Use Headline Inflation of {raw['inflation_used']}% for your macro assessment.
            2. Dividend tracking metrics must be ignored if the period analyzed is Q1 or Q3.
            3. Critically evaluate current price (₦{raw['current_sp']}) against Projected Forward EPS (₦{raw['forward_eps']}) using The Forward Projector Rule.
            4. Assess the Layer 2 Value-Momentum Matrix classification (**{mom.get('matrix_status')}**) to guide timing and entry strategy.
            {"5. Assess Cost-to-Income and ROE stability for banking performance." if is_bank else "5. Assess ROIC and Free Cash Flow conversion quality."}

            Format your output exactly with these 4 structural markdown headers:
            ### 1. Efficiency Check
            ### 2. Cash & Dividend Safety
            ### 3. Valuation & Trajectory Verdict (Apply Forward Projector & Momentum Rule here)
            ### 4. Risk & Macro Verdict

            Focus your tone on whether the business is an operational 'Wealth Creator' or 'Wealth Destroyer' based on Real {'ROE' if is_bank else 'ROIC'}.

            STRICT FORMATTING RULES:
            1. Always wrap key numbers, financial metrics, and critical verdicts in double asterisks, e.g., **₦80.73 billion**, **15.97%**, or **HOLD / ACCUMULATE**.
            2. DO NOT use TeX/LaTeX fractions like {{a}}/{{b}}, $\le$, $\ge$, or $. Use simple text like (₦74.60 / ₦6.00) and <= or >=.
            3. Every bullet point MUST start on its own fresh line beginning with an asterisk (*).
            """

            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error generating AI memo: {str(e)}"
